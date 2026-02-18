from datetime import datetime, timezone
import threading

from task_automation_studio.core.teach_models import TeachEventData, TeachEventType
from task_automation_studio.services.session_replay import (
    _button_name_to_key,
    _event_time_ms,
    _is_escape_key,
    _key_name_to_key,
    _modifier_name_to_key,
    _normalize_speed_factor,
    _resolve_click_target,
    _sleep_with_stop,
    TeachSessionReplayer,
)


class _MouseStub:
    class Button:
        left = "LEFT"
        right = "RIGHT"
        middle = "MIDDLE"


class _KeyStub:
    class Key:
        enter = "ENTER"
        esc = "ESC"
        ctrl = "CTRL"
        shift = "SHIFT"
        alt = "ALT"
        cmd = "CMD"


class _KeyboardControllerStub:
    def __init__(self) -> None:
        self.actions: list[tuple[str, str]] = []

    def press(self, key) -> None:  # type: ignore[no-untyped-def]
        self.actions.append(("press", str(key)))

    def release(self, key) -> None:  # type: ignore[no-untyped-def]
        self.actions.append(("release", str(key)))


class _MouseControllerStub:
    def __init__(self) -> None:
        self.position = (0, 0)

    def click(self, *_args):  # type: ignore[no-untyped-def]
        return None

    def scroll(self, *_args):  # type: ignore[no-untyped-def]
        return None


def test_normalize_speed_factor() -> None:
    assert _normalize_speed_factor(1.5) == 1.5
    assert _normalize_speed_factor(0) == 1.0
    assert _normalize_speed_factor(99) == 10.0


def test_event_time_ms_prefers_payload() -> None:
    event = TeachEventData(
        event_id="e1",
        event_type=TeachEventType.KEY_PRESS,
        payload={"t_ms": 1234},
        timestamp=datetime.now(timezone.utc),
    )
    assert _event_time_ms(event) == 1234


def test_button_name_to_key() -> None:
    assert _button_name_to_key("left", _MouseStub) == "LEFT"
    assert _button_name_to_key("right", _MouseStub) == "RIGHT"


def test_key_name_to_key() -> None:
    assert _key_name_to_key("enter", _KeyStub) == "ENTER"
    assert _key_name_to_key("a", _KeyStub) == "a"


def test_modifier_name_to_key() -> None:
    assert _modifier_name_to_key("ctrl", _KeyStub) == "CTRL"


def test_apply_hotkey_event() -> None:
    event = TeachEventData(
        event_id="e_hotkey",
        event_type=TeachEventType.HOTKEY,
        payload={"key": "v", "modifiers": ["ctrl"]},
        timestamp=datetime.now(timezone.utc),
    )
    keyboard_controller = _KeyboardControllerStub()
    mouse_controller = _MouseControllerStub()

    replayer = TeachSessionReplayer(session_service=None)  # type: ignore[arg-type]
    applied = replayer._apply_event(  # type: ignore[attr-defined]
        event=event,
        mouse_module=_MouseStub,
        keyboard_module=_KeyStub,
        mouse_controller=mouse_controller,
        keyboard_controller=keyboard_controller,
    )

    assert applied is True
    assert keyboard_controller.actions == [
        ("press", "CTRL"),
        ("press", "v"),
        ("release", "v"),
        ("release", "CTRL"),
    ]


def test_apply_mouse_click_prefers_smart_locator() -> None:
    event = TeachEventData(
        event_id="e_click",
        event_type=TeachEventType.MOUSE_CLICK,
        payload={"x": 10, "y": 20, "button": "left", "smart_locator": {"version": 1, "anchors": []}},
        timestamp=datetime.now(timezone.utc),
    )

    class _MouseControllerCapture(_MouseControllerStub):
        def __init__(self) -> None:
            super().__init__()
            self.clicked = False

        def click(self, *_args):  # type: ignore[no-untyped-def]
            self.clicked = True
            return None

    from task_automation_studio.services import session_replay as sr

    original = sr.resolve_smart_click_position
    sr.resolve_smart_click_position = lambda _payload: (44, 66)  # type: ignore[assignment]
    try:
        keyboard_controller = _KeyboardControllerStub()
        mouse_controller = _MouseControllerCapture()
        replayer = TeachSessionReplayer(session_service=None)  # type: ignore[arg-type]
        applied = replayer._apply_event(  # type: ignore[attr-defined]
            event=event,
            mouse_module=_MouseStub,
            keyboard_module=_KeyStub,
            mouse_controller=mouse_controller,
            keyboard_controller=keyboard_controller,
        )
    finally:
        sr.resolve_smart_click_position = original  # type: ignore[assignment]

    assert applied is True
    assert mouse_controller.position == (44, 66)
    assert mouse_controller.clicked is True


def test_apply_mouse_click_fails_without_target() -> None:
    event = TeachEventData(
        event_id="e_click_missing",
        event_type=TeachEventType.MOUSE_CLICK,
        payload={"button": "left"},
        timestamp=datetime.now(timezone.utc),
    )

    class _MouseControllerCapture(_MouseControllerStub):
        def __init__(self) -> None:
            super().__init__()
            self.clicked = False

        def click(self, *_args):  # type: ignore[no-untyped-def]
            self.clicked = True
            return None

    keyboard_controller = _KeyboardControllerStub()
    mouse_controller = _MouseControllerCapture()
    replayer = TeachSessionReplayer(session_service=None)  # type: ignore[arg-type]
    applied = replayer._apply_event(  # type: ignore[attr-defined]
        event=event,
        mouse_module=_MouseStub,
        keyboard_module=_KeyStub,
        mouse_controller=mouse_controller,
        keyboard_controller=keyboard_controller,
    )

    assert applied is False
    assert mouse_controller.clicked is False


def test_resolve_click_target_fallback_to_coordinates() -> None:
    assert _resolve_click_target({"x": 12, "y": 99}) == (12, 99)


def test_is_escape_key() -> None:
    class _Esc:
        def __str__(self) -> str:
            return "Key.esc"

    class _CharEsc:
        char = "\x1b"

        def __str__(self) -> str:
            return "x"

    assert _is_escape_key(_Esc()) is True
    assert _is_escape_key(_CharEsc()) is True


def test_sleep_with_stop() -> None:
    stop = threading.Event()
    stop.set()
    assert _sleep_with_stop(0.5, stop) is False
