from task_automation_studio.services.auto_recorder import _button_to_name, _key_to_name


class _FakeKey:
    def __init__(self, char: str | None = None, fallback: str = "Key.enter") -> None:
        self.char = char
        self._fallback = fallback

    def __str__(self) -> str:
        return self._fallback


def test_button_to_name() -> None:
    assert _button_to_name("Button.left") == "left"
    assert _button_to_name("left") == "left"


def test_key_to_name() -> None:
    assert _key_to_name(_FakeKey(char="a")) == "a"
    assert _key_to_name(_FakeKey(char=None, fallback="Key.esc")) == "esc"
