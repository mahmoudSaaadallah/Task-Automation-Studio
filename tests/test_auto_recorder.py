import time
from pathlib import Path

from task_automation_studio.core.teach_models import TeachEventType
from task_automation_studio.services.auto_recorder import AutoTeachRecorder, _button_to_name, _key_to_name


class _FakeKey:
    def __init__(self, char: str | None = None, fallback: str = "Key.enter") -> None:
        self.char = char
        self._fallback = fallback

    def __str__(self) -> str:
        return self._fallback


class _FakeSessionService:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []
        self.finished: list[str] = []

    def add_event(self, **kwargs):  # type: ignore[no-untyped-def]
        self.events.append(kwargs)
        return None

    def finish_session(self, *, session_id: str) -> None:
        self.finished.append(session_id)

    def artifacts_dir(self) -> Path:
        return Path("artifacts")


class _FailingSessionService(_FakeSessionService):
    def add_event(self, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("db locked")


def test_button_to_name() -> None:
    assert _button_to_name("Button.left") == "left"
    assert _button_to_name("left") == "left"


def test_key_to_name() -> None:
    assert _key_to_name(_FakeKey(char="a")) == "a"
    assert _key_to_name(_FakeKey(char=None, fallback="Key.esc")) == "esc"


def test_hotkey_recording_ctrl_v() -> None:
    service = _FakeSessionService()
    recorder = AutoTeachRecorder(session_service=service)
    recorder._session_id = "session-1"  # type: ignore[attr-defined]
    recorder._running = True  # type: ignore[attr-defined]
    recorder._start_ts = time.perf_counter()  # type: ignore[attr-defined]

    recorder._on_key_press(_FakeKey(char=None, fallback="Key.ctrl"))  # type: ignore[attr-defined]
    recorder._on_key_press(_FakeKey(char="v"))  # type: ignore[attr-defined]

    assert len(service.events) == 1
    event = service.events[0]
    assert event["event_type"] == TeachEventType.HOTKEY
    payload = event["payload"]
    assert isinstance(payload, dict)
    assert payload["key"] == "v"
    assert payload["modifiers"] == ["ctrl"]


def test_mouse_click_records_smart_locator_payload() -> None:
    service = _FakeSessionService()
    recorder = AutoTeachRecorder(session_service=service)
    recorder._session_id = "session-1"  # type: ignore[attr-defined]
    recorder._running = True  # type: ignore[attr-defined]
    recorder._start_ts = time.perf_counter()  # type: ignore[attr-defined]
    recorder._capture_smart_locator = lambda **_kwargs: {  # type: ignore[method-assign, assignment]
        "version": 1,
        "anchors": [{"anchor_id": "target", "path": "x.png", "dx": 0, "dy": 0, "weight": 1.0}],
    }
    recorder._active_window_context = lambda: {"title": "Example"}  # type: ignore[method-assign, assignment]

    recorder._on_click(100, 200, "Button.left", True)  # type: ignore[attr-defined]

    assert len(service.events) == 1
    event = service.events[0]
    assert event["event_type"] == TeachEventType.MOUSE_CLICK
    assert isinstance(event["payload"], dict)
    payload = event["payload"]
    assert isinstance(payload, dict)
    assert payload["smart_locator"]["version"] == 1
    assert payload["window_context"]["title"] == "Example"
    assert event["event_id"]


def test_mouse_click_callback_does_not_raise_when_add_event_fails() -> None:
    service = _FailingSessionService()
    recorder = AutoTeachRecorder(session_service=service)
    recorder._session_id = "session-1"  # type: ignore[attr-defined]
    recorder._running = True  # type: ignore[attr-defined]
    recorder._start_ts = time.perf_counter()  # type: ignore[attr-defined]
    recorder._capture_smart_locator = lambda **_kwargs: None  # type: ignore[method-assign, assignment]
    recorder._active_window_context = lambda: None  # type: ignore[method-assign, assignment]

    recorder._on_click(100, 200, "Button.left", True)  # type: ignore[attr-defined]
    recorder._on_key_press(_FakeKey(char="a"))  # type: ignore[attr-defined]
