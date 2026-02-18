from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from task_automation_studio.core.teach_models import TeachEventData, TeachEventType
from task_automation_studio.services.teach_sessions import TeachSessionService

SEARCH_RADIUS_PX = 140
TEMPLATE_MATCH_CONFIDENCE = 0.92
TEMPLATE_DEDUP_DISTANCE_PX = 10


def _normalize_speed_factor(value: float) -> float:
    if value <= 0:
        return 1.0
    return min(value, 10.0)


def _is_escape_key(key: Any) -> bool:
    char = getattr(key, "char", None)
    if isinstance(char, str) and char.lower() == "\x1b":
        return True
    key_name = str(key).lower()
    return key_name in {"key.esc", "esc"}


def _sleep_with_stop(total_seconds: float, stop_event: threading.Event) -> bool:
    remaining = max(0.0, total_seconds)
    while remaining > 0:
        if stop_event.is_set():
            return False
        chunk = min(0.05, remaining)
        time.sleep(chunk)
        remaining -= chunk
    return not stop_event.is_set()


def _safe_region(*, left: int, top: int, width: int, height: int) -> tuple[int, int, int, int] | None:
    if width <= 0 or height <= 0:
        return None
    return max(0, left), max(0, top), width, height


def _region_around_point(x: int, y: int, radius: int) -> tuple[int, int, int, int] | None:
    left = x - radius
    top = y - radius
    return _safe_region(left=left, top=top, width=radius * 2, height=radius * 2)


def _window_titles_match(recorded_title: str, active_title: str) -> bool:
    left = recorded_title.strip().lower()
    right = active_title.strip().lower()
    if not left or not right:
        return False
    return left in right or right in left


def _active_window_region(expected_title: str | None = None) -> tuple[int, int, int, int] | None:
    try:
        import pygetwindow as gw  # pylint: disable=import-outside-toplevel
    except Exception:  # pragma: no cover - dependency/platform dependent
        return None

    try:
        window = gw.getActiveWindow()
    except Exception:  # pragma: no cover - OS/window-manager dependent
        return None
    if window is None:
        return None

    active_title = str(getattr(window, "title", "")).strip()
    if expected_title and not _window_titles_match(expected_title, active_title):
        return None

    left = getattr(window, "left", None)
    top = getattr(window, "top", None)
    width = getattr(window, "width", None)
    height = getattr(window, "height", None)
    if not all(isinstance(value, int) for value in (left, top, width, height)):
        return None
    return _safe_region(left=left, top=top, width=width, height=height)


def _candidate_search_regions(payload: dict[str, Any], *, dx: int, dy: int) -> list[tuple[int, int, int, int]]:
    regions: list[tuple[int, int, int, int]] = []

    x = payload.get("x")
    y = payload.get("y")
    if isinstance(x, int) and isinstance(y, int):
        nearby = _region_around_point(x + dx, y + dy, SEARCH_RADIUS_PX)
        if nearby is not None:
            regions.append(nearby)

    window_context = payload.get("window_context")
    if isinstance(window_context, dict):
        recorded_title = window_context.get("title")
        expected_title = recorded_title if isinstance(recorded_title, str) else None
        active_region = _active_window_region(expected_title=expected_title)
        if active_region is not None:
            regions.append(active_region)
        else:
            left = window_context.get("left")
            top = window_context.get("top")
            width = window_context.get("width")
            height = window_context.get("height")
            if all(isinstance(value, int) for value in (left, top, width, height)):
                recorded_region = _safe_region(left=left, top=top, width=width, height=height)
                if recorded_region is not None:
                    regions.append(recorded_region)

    unique_regions: list[tuple[int, int, int, int]] = []
    for region in regions:
        if region not in unique_regions:
            unique_regions.append(region)
    return unique_regions


def _dedupe_centers(centers: list[tuple[int, int]], *, min_distance_px: int) -> list[tuple[int, int]]:
    unique: list[tuple[int, int]] = []
    for center in centers:
        if any(abs(center[0] - item[0]) <= min_distance_px and abs(center[1] - item[1]) <= min_distance_px for item in unique):
            continue
        unique.append(center)
    return unique


def _locate_template_centers(
    template_path: str, *, region: tuple[int, int, int, int] | None = None, confidence: float = TEMPLATE_MATCH_CONFIDENCE
) -> list[tuple[int, int]]:
    path = Path(template_path)
    if not path.exists():
        return []
    try:
        import pyautogui  # pylint: disable=import-outside-toplevel
    except Exception:  # pragma: no cover - dependency/platform dependent
        return []

    try:
        kwargs: dict[str, Any] = {"grayscale": True}
        if region is not None:
            kwargs["region"] = region

        try:
            boxes = list(pyautogui.locateAllOnScreen(str(path), confidence=confidence, **kwargs))
        except TypeError:
            # confidence requires OpenCV; fall back to backend default when unavailable.
            boxes = list(pyautogui.locateAllOnScreen(str(path), **kwargs))
    except Exception:  # pragma: no cover - screen/env dependent
        return []

    centers: list[tuple[int, int]] = []
    for box in boxes:
        center = pyautogui.center(box)
        centers.append((int(center.x), int(center.y)))
    return _dedupe_centers(centers, min_distance_px=TEMPLATE_DEDUP_DISTANCE_PX)


def _single_unique_center(centers: list[tuple[int, int]]) -> tuple[int, int] | None:
    if len(centers) != 1:
        return None
    return centers[0]


def _locate_template_center(template_path: str, *, region: tuple[int, int, int, int] | None = None) -> tuple[int, int] | None:
    centers = _locate_template_centers(template_path, region=region, confidence=TEMPLATE_MATCH_CONFIDENCE)
    return _single_unique_center(centers)


def _resolve_template_click_position(payload: dict[str, Any]) -> tuple[int, int] | None:
    candidates = payload.get("template_candidates")
    if isinstance(candidates, list):
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            path = candidate.get("path")
            dx = candidate.get("dx")
            dy = candidate.get("dy")
            if not isinstance(path, str) or not path:
                continue
            if not isinstance(dx, int) or not isinstance(dy, int):
                continue
            regions = _candidate_search_regions(payload, dx=dx, dy=dy)
            search_regions: list[tuple[int, int, int, int] | None] = list(regions)
            if not search_regions:
                search_regions = [None]
            for region in search_regions:
                center = _locate_template_center(path, region=region)
                if center is None:
                    continue
                return center[0] - dx, center[1] - dy

    template_path = payload.get("template_path")
    if isinstance(template_path, str) and template_path:
        regions = _candidate_search_regions(payload, dx=0, dy=0)
        search_regions: list[tuple[int, int, int, int] | None] = list(regions)
        if not search_regions:
            search_regions = [None]
        for region in search_regions:
            center = _locate_template_center(template_path, region=region)
            if center is not None:
                return center
    return None


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
    stopped_by_user: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "replayed_events": self.replayed_events,
            "skipped_events": self.skipped_events,
            "speed_factor": self.speed_factor,
            "stopped_by_user": self.stopped_by_user,
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
            return ReplaySummary(
                session_id=session_id,
                replayed_events=0,
                skipped_events=0,
                speed_factor=1.0,
                stopped_by_user=False,
            )

        safe_speed = _normalize_speed_factor(speed_factor)
        mouse_controller = mouse.Controller()
        keyboard_controller = keyboard.Controller()
        stop_event = threading.Event()

        def _on_stop_key(key: Any) -> bool | None:
            if _is_escape_key(key):
                stop_event.set()
                return False
            return None

        stop_listener = keyboard.Listener(on_press=_on_stop_key)
        stop_listener.start()

        replayed_count = 0
        skipped_count = 0
        previous_time = _event_time_ms(events[0])

        for event in events:
            if stop_event.is_set():
                break
            current_time = _event_time_ms(event)
            delay_seconds = max(0, current_time - previous_time) / 1000 / safe_speed
            if delay_seconds > 0:
                if not _sleep_with_stop(delay_seconds, stop_event):
                    break
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

        stop_listener.stop()
        return ReplaySummary(
            session_id=session_id,
            replayed_events=replayed_count,
            skipped_events=skipped_count,
            speed_factor=safe_speed,
            stopped_by_user=stop_event.is_set(),
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

            resolved_position = _resolve_template_click_position(event.payload)
            if resolved_position is not None:
                x, y = resolved_position
            elif "template_candidates" in event.payload or "template_path" in event.payload:
                # Template-based events should never fall back to blind absolute coordinates.
                return False

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
