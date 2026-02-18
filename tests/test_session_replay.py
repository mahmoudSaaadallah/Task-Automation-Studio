from datetime import datetime, timezone
from pathlib import Path
import threading

from task_automation_studio.core.teach_models import TeachEventData, TeachEventType
from task_automation_studio.services.session_replay import (
    ReplaySummary,
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
    result = replayer._apply_event(  # type: ignore[attr-defined]
        event=event,
        mouse_module=_MouseStub,
        keyboard_module=_KeyStub,
        mouse_controller=mouse_controller,
        keyboard_controller=keyboard_controller,
    )

    assert result.applied is True
    assert keyboard_controller.actions == [
        ("press", "CTRL"),
        ("press", "v"),
        ("release", "v"),
        ("release", "CTRL"),
    ]


def test_apply_key_press_event() -> None:
    event = TeachEventData(
        event_id="e_key",
        event_type=TeachEventType.KEY_PRESS,
        payload={"key": "a"},
        timestamp=datetime.now(timezone.utc),
    )
    keyboard_controller = _KeyboardControllerStub()
    mouse_controller = _MouseControllerStub()
    replayer = TeachSessionReplayer(session_service=None)  # type: ignore[arg-type]

    result = replayer._apply_event(  # type: ignore[attr-defined]
        event=event,
        mouse_module=_MouseStub,
        keyboard_module=_KeyStub,
        mouse_controller=mouse_controller,
        keyboard_controller=keyboard_controller,
    )
    assert result.applied is True
    assert keyboard_controller.actions == [("press", "a"), ("release", "a")]


def test_apply_key_press_event_rejects_escape() -> None:
    event = TeachEventData(
        event_id="e_key_esc",
        event_type=TeachEventType.KEY_PRESS,
        payload={"key": "esc"},
        timestamp=datetime.now(timezone.utc),
    )
    keyboard_controller = _KeyboardControllerStub()
    mouse_controller = _MouseControllerStub()
    replayer = TeachSessionReplayer(session_service=None)  # type: ignore[arg-type]

    result = replayer._apply_event(  # type: ignore[attr-defined]
        event=event,
        mouse_module=_MouseStub,
        keyboard_module=_KeyStub,
        mouse_controller=mouse_controller,
        keyboard_controller=keyboard_controller,
    )
    assert result.applied is False
    assert keyboard_controller.actions == []


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
        result = replayer._apply_event(  # type: ignore[attr-defined]
            event=event,
            mouse_module=_MouseStub,
            keyboard_module=_KeyStub,
            mouse_controller=mouse_controller,
            keyboard_controller=keyboard_controller,
        )
    finally:
        sr.resolve_smart_click_position = original  # type: ignore[assignment]

    assert result.applied is True
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
    result = replayer._apply_event(  # type: ignore[attr-defined]
        event=event,
        mouse_module=_MouseStub,
        keyboard_module=_KeyStub,
        mouse_controller=mouse_controller,
        keyboard_controller=keyboard_controller,
    )

    assert result.applied is False
    assert mouse_controller.clicked is False


def test_resolve_click_target_fallback_to_coordinates() -> None:
    assert _resolve_click_target({"x": 12, "y": 99}) == (12, 99)


def test_apply_hotkey_event_invalid_payload() -> None:
    event = TeachEventData(
        event_id="e_hotkey_bad",
        event_type=TeachEventType.HOTKEY,
        payload={"key": "v", "modifiers": "ctrl"},
        timestamp=datetime.now(timezone.utc),
    )
    keyboard_controller = _KeyboardControllerStub()
    mouse_controller = _MouseControllerStub()
    replayer = TeachSessionReplayer(session_service=None)  # type: ignore[arg-type]

    result = replayer._apply_event(  # type: ignore[attr-defined]
        event=event,
        mouse_module=_MouseStub,
        keyboard_module=_KeyStub,
        mouse_controller=mouse_controller,
        keyboard_controller=keyboard_controller,
    )
    assert result.applied is False
    assert keyboard_controller.actions == []


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


def test_replay_summary_to_dict_includes_diagnostics() -> None:
    summary = ReplaySummary(
        session_id="s1",
        replayed_events=2,
        skipped_events=1,
        speed_factor=1.0,
        stopped_by_user=False,
        diagnostics=[{"event_id": "e1", "applied": False, "reason": "agent_failed", "details": {}}],
    )
    payload = summary.to_dict()
    assert payload["session_id"] == "s1"
    assert isinstance(payload["diagnostics"], list)
    assert payload["diagnostics"][0]["reason"] == "agent_failed"
    assert payload["diagnostics_file"] is None


def test_save_diagnostics_writes_json(tmp_path: Path) -> None:
    class _Service:
        def artifacts_dir(self) -> Path:
            return tmp_path

    replayer = TeachSessionReplayer(session_service=_Service())  # type: ignore[arg-type]
    summary = ReplaySummary(
        session_id="s2",
        replayed_events=1,
        skipped_events=0,
        speed_factor=1.0,
        stopped_by_user=False,
        diagnostics=[{"event_id": "e2", "applied": True, "reason": "ok", "details": {}}],
    )
    output = replayer.save_diagnostics(summary=summary)
    assert output.exists()
    content = output.read_text(encoding="utf-8")
    assert '"session_id": "s2"' in content
