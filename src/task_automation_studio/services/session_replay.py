from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from task_automation_studio.core.teach_models import TeachEventData, TeachEventType
from task_automation_studio.services.teach_sessions import TeachSessionService


def _normalize_speed_factor(value: float) -> float:
    if value <= 0:
        return 1.0
    return min(value, 10.0)


def _event_time_ms(event: TeachEventData) -> int:
    payload_time = event.payload.get("t_ms")
    if isinstance(payload_time, int):
        return max(payload_time, 0)
    return int(event.timestamp.timestamp() * 1000)


def _button_name_to_key(name: str, mouse_module: Any) -> Any:
    normalized = name.lower()
    if normalized == "left":
        return mouse_module.Button.left
    if normalized == "right":
        return mouse_module.Button.right
    if normalized == "middle":
        return mouse_module.Button.middle
    return mouse_module.Button.left


def _key_name_to_key(name: str, keyboard_module: Any) -> Any:
    normalized = name.lower()
    special = getattr(keyboard_module.Key, normalized, None)
    if special is not None:
        return special
    return normalized


def _modifier_name_to_key(name: str, keyboard_module: Any) -> Any:
    normalized = name.lower()
    if normalized == "ctrl":
        key = getattr(keyboard_module.Key, "ctrl", None) or getattr(keyboard_module.Key, "ctrl_l", None)
        return key
    if normalized == "alt":
        key = getattr(keyboard_module.Key, "alt", None) or getattr(keyboard_module.Key, "alt_l", None)
        return key
    if normalized == "shift":
        key = getattr(keyboard_module.Key, "shift", None) or getattr(keyboard_module.Key, "shift_l", None)
        return key
    if normalized == "cmd":
        key = getattr(keyboard_module.Key, "cmd", None)
        if key is None:
            key = getattr(keyboard_module.Key, "cmd_l", None)
        return key
    return None


@dataclass(slots=True)
class ReplaySummary:
    session_id: str
    replayed_events: int
    skipped_events: int
    speed_factor: float

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "replayed_events": self.replayed_events,
            "skipped_events": self.skipped_events,
            "speed_factor": self.speed_factor,
        }


class TeachSessionReplayer:
    """Replay teach session events using global mouse/keyboard controllers."""

    def __init__(self, session_service: TeachSessionService) -> None:
        self._service = session_service

    def replay(self, *, session_id: str, speed_factor: float = 1.0) -> ReplaySummary:
        try:
            from pynput import keyboard, mouse  # pylint: disable=import-outside-toplevel
        except Exception as exc:  # pragma: no cover - platform/import dependent
            raise RuntimeError("Replay requires 'pynput'. Install dependencies with: pip install -e .[dev]") from exc

        session = self._service.get_session(session_id=session_id)
        events = sorted(session.events, key=lambda item: item.timestamp)
        if not events:
            return ReplaySummary(session_id=session_id, replayed_events=0, skipped_events=0, speed_factor=1.0)

        safe_speed = _normalize_speed_factor(speed_factor)
        mouse_controller = mouse.Controller()
        keyboard_controller = keyboard.Controller()

        replayed_count = 0
        skipped_count = 0
        previous_time = _event_time_ms(events[0])

        for event in events:
            current_time = _event_time_ms(event)
            delay_seconds = max(0, current_time - previous_time) / 1000 / safe_speed
            if delay_seconds > 0:
                time.sleep(delay_seconds)
            previous_time = current_time

            applied = self._apply_event(
                event=event,
                mouse_module=mouse,
                keyboard_module=keyboard,
                mouse_controller=mouse_controller,
                keyboard_controller=keyboard_controller,
            )
            if applied:
                replayed_count += 1
            else:
                skipped_count += 1

        return ReplaySummary(
            session_id=session_id,
            replayed_events=replayed_count,
            skipped_events=skipped_count,
            speed_factor=safe_speed,
        )

    def _apply_event(
        self,
        *,
        event: TeachEventData,
        mouse_module: Any,
        keyboard_module: Any,
        mouse_controller: Any,
        keyboard_controller: Any,
    ) -> bool:
        if event.event_type == TeachEventType.MOUSE_CLICK:
            x = event.payload.get("x")
            y = event.payload.get("y")
            button_name = str(event.payload.get("button", "left"))
            if isinstance(x, int) and isinstance(y, int):
                mouse_controller.position = (x, y)
            mouse_controller.click(_button_name_to_key(button_name, mouse_module), 1)
            return True

        if event.event_type == TeachEventType.MOUSE_SCROLL:
            x = event.payload.get("x")
            y = event.payload.get("y")
            if isinstance(x, int) and isinstance(y, int):
                mouse_controller.position = (x, y)
            dx = int(event.payload.get("dx", 0))
            dy = int(event.payload.get("dy", 0))
            mouse_controller.scroll(dx, dy)
            return True

        if event.event_type == TeachEventType.KEY_PRESS:
            key_name = str(event.payload.get("key", "")).lower()
            if not key_name or key_name == "esc":
                return False
            key = _key_name_to_key(key_name, keyboard_module)
            keyboard_controller.press(key)
            keyboard_controller.release(key)
            return True

        if event.event_type == TeachEventType.HOTKEY:
            key_name = str(event.payload.get("key", "")).lower()
            modifiers_payload = event.payload.get("modifiers", [])
            if not key_name or not isinstance(modifiers_payload, list):
                return False

            pressed_modifiers: list[Any] = []
            for modifier_name in [str(item).lower() for item in modifiers_payload]:
                modifier_key = _modifier_name_to_key(modifier_name, keyboard_module)
                if modifier_key is None:
                    continue
                keyboard_controller.press(modifier_key)
                pressed_modifiers.append(modifier_key)

            target_key = _key_name_to_key(key_name, keyboard_module)
            keyboard_controller.press(target_key)
            keyboard_controller.release(target_key)

            for modifier_key in reversed(pressed_modifiers):
                keyboard_controller.release(modifier_key)
            return True

        return False
