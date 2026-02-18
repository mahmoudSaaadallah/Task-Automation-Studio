from datetime import datetime, timezone

from task_automation_studio.core.teach_models import TeachEventData, TeachEventType
from task_automation_studio.services.session_replay import (
    _button_name_to_key,
    _event_time_ms,
    _key_name_to_key,
    _modifier_name_to_key,
    _normalize_speed_factor,
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
