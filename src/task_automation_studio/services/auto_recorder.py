from __future__ import annotations

import threading
import time
from typing import Any
from pathlib import Path
from uuid import uuid4

from task_automation_studio.core.teach_models import TeachEventType
from task_automation_studio.services.teach_sessions import TeachSessionService


MODIFIER_NAMES = {"ctrl", "alt", "shift", "cmd"}


def _button_to_name(button: Any) -> str:
    name = str(button)
    if "." in name:
        return name.split(".", 1)[1].lower()
    return name.lower()


def _key_to_name(key: Any) -> str:
    char = getattr(key, "char", None)
    if char:
        return str(char).lower()
    name = str(key)
    if name.lower().startswith("key."):
        return name.split(".", 1)[1].lower()
    return name.lower()


def _canonical_modifier_name(key_name: str) -> str | None:
    lowered = key_name.lower()
    if lowered.startswith("ctrl"):
        return "ctrl"
    if lowered.startswith("alt"):
        return "alt"
    if lowered.startswith("shift"):
        return "shift"
    if lowered.startswith("cmd") or lowered.startswith("win") or lowered.startswith("super"):
        return "cmd"
    return None


class AutoTeachRecorder:
    """Global mouse/keyboard recorder for teach sessions.

    Recording starts immediately and stops when ESC is pressed or stop() is called.
    """

    def __init__(self, session_service: TeachSessionService) -> None:
        self._service = session_service
        self._session_id: str | None = None
        self._running = False
        self._start_ts: float = 0.0
        self._lock = threading.Lock()
        self._stopped_event = threading.Event()
        self._mouse_listener: Any = None
        self._keyboard_listener: Any = None
        self._pressed_modifiers: set[str] = set()
        self._pressed_keys: set[str] = set()

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._running

    def start(self, *, session_id: str) -> None:
        with self._lock:
            if self._running:
                raise ValueError("Recorder is already running.")

            try:
                from pynput import keyboard, mouse  # pylint: disable=import-outside-toplevel
            except Exception as exc:  # pragma: no cover - platform/import dependent
                raise RuntimeError(
                    "Auto recorder requires 'pynput'. Install dependencies with: pip install -e .[dev]"
                ) from exc

            self._session_id = session_id
            self._running = True
            self._start_ts = time.perf_counter()
            self._stopped_event.clear()
            self._pressed_modifiers.clear()
            self._pressed_keys.clear()

            self._mouse_listener = mouse.Listener(on_click=self._on_click, on_scroll=self._on_scroll)
            self._keyboard_listener = keyboard.Listener(on_press=self._on_key_press, on_release=self._on_key_release)
            self._mouse_listener.start()
            self._keyboard_listener.start()

    def stop(self, *, finish_session: bool = True) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False
            session_id = self._session_id
            mouse_listener = self._mouse_listener
            keyboard_listener = self._keyboard_listener
            self._mouse_listener = None
            self._keyboard_listener = None

        if mouse_listener is not None:
            mouse_listener.stop()
        if keyboard_listener is not None:
            keyboard_listener.stop()

        if finish_session and session_id:
            self._service.finish_session(session_id=session_id)
        self._stopped_event.set()

    def wait_until_stopped(self, timeout: float | None = None) -> bool:
        return self._stopped_event.wait(timeout=timeout)

    def _elapsed_ms(self) -> int:
        return int((time.perf_counter() - self._start_ts) * 1000)

    def _on_click(self, x: int, y: int, button: Any, pressed: bool) -> None:
        if not pressed or not self.is_recording:
            return
        session_id = self._session_id
        if not session_id:
            return
        event_id = uuid4().hex
        template_path = self._capture_click_template(session_id=session_id, x=x, y=y, event_id=event_id)
        payload: dict[str, Any] = {"x": x, "y": y, "button": _button_to_name(button), "t_ms": self._elapsed_ms()}
        if template_path is not None:
            payload["template_path"] = str(template_path)
        self._service.add_event(
            session_id=session_id,
            event_type=TeachEventType.MOUSE_CLICK,
            payload=payload,
            event_id=event_id,
            sensitive=False,
        )

    def _on_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        if not self.is_recording:
            return
        session_id = self._session_id
        if not session_id:
            return
        self._service.add_event(
            session_id=session_id,
            event_type=TeachEventType.MOUSE_SCROLL,
            payload={"x": x, "y": y, "dx": dx, "dy": dy, "t_ms": self._elapsed_ms()},
            sensitive=False,
        )

    def _on_key_press(self, key: Any) -> bool | None:
        if not self.is_recording:
            return None
        session_id = self._session_id
        if not session_id:
            return None

        key_name = _key_to_name(key)
        if key_name == "esc":
            self.stop(finish_session=True)
            return False

        modifier_name = _canonical_modifier_name(key_name)
        if modifier_name:
            self._pressed_modifiers.add(modifier_name)
            return None

        if key_name in self._pressed_keys:
            return None
        self._pressed_keys.add(key_name)

        if self._pressed_modifiers:
            ordered_modifiers = [m for m in ("ctrl", "alt", "shift", "cmd") if m in self._pressed_modifiers]
            combo = "+".join([*ordered_modifiers, key_name])
            self._service.add_event(
                session_id=session_id,
                event_type=TeachEventType.HOTKEY,
                payload={
                    "key": key_name,
                    "modifiers": ordered_modifiers,
                    "combo": combo,
                    "t_ms": self._elapsed_ms(),
                },
                sensitive=False,
            )
            return None

        self._service.add_event(
            session_id=session_id,
            event_type=TeachEventType.KEY_PRESS,
            payload={"key": key_name, "t_ms": self._elapsed_ms()},
            sensitive=False,
        )
        return None

    def _on_key_release(self, key: Any) -> None:
        if not self.is_recording:
            return
        key_name = _key_to_name(key)
        modifier_name = _canonical_modifier_name(key_name)
        if modifier_name:
            self._pressed_modifiers.discard(modifier_name)
            return
        self._pressed_keys.discard(key_name)

    def _capture_click_template(self, *, session_id: str, x: int, y: int, event_id: str) -> Path | None:
        try:
            from PIL import ImageGrab  # pylint: disable=import-outside-toplevel
        except Exception:  # pragma: no cover - dependency/platform dependent
            return None

        artifact_root = self._service.artifacts_dir() / "click_templates" / session_id
        artifact_root.mkdir(parents=True, exist_ok=True)

        half_size = 24
        left = max(0, x - half_size)
        top = max(0, y - half_size)
        right = max(left + 1, x + half_size)
        bottom = max(top + 1, y + half_size)

        try:
            image = ImageGrab.grab(bbox=(left, top, right, bottom))
        except Exception:  # pragma: no cover - OS/screen dependent
            return None

        path = artifact_root / f"{event_id}.png"
        try:
            image.save(path)
        except Exception:  # pragma: no cover - filesystem dependent
            return None
        return path
