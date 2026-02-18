from __future__ import annotations

import pytest

from task_automation_studio.app import _parse_payload_json, build_parser


def test_parse_payload_json_accepts_object() -> None:
    payload = _parse_payload_json('{"selector":"#email","value":"x"}')
    assert payload["selector"] == "#email"


def test_parse_payload_json_rejects_non_object() -> None:
    with pytest.raises(ValueError, match="Payload JSON must be an object"):
        _parse_payload_json('["not","object"]')


def test_parser_supports_teach_start() -> None:
    parser = build_parser()
    args = parser.parse_args(["teach", "start", "--name", "session A"])
    assert args.command == "teach"
    assert args.teach_command == "start"
    assert args.name == "session A"
