import time

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
