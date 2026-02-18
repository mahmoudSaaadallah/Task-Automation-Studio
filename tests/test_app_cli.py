from __future__ import annotations

import pytest

from task_automation_studio.app import _parse_payload_json, _parse_payload_pairs, build_parser


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


def test_parse_payload_pairs() -> None:
    payload = _parse_payload_pairs(["selector=input[name=email]", "value={{record.email}}"])
    assert payload["selector"] == "input[name=email]"
    assert payload["value"] == "{{record.email}}"


def test_parser_supports_workflow_validate() -> None:
    parser = build_parser()
    args = parser.parse_args(["workflow", "validate", "--workflow-file", "x.json"])
    assert args.command == "workflow"
    assert args.workflow_command == "validate"


def test_parser_supports_teach_record() -> None:
    parser = build_parser()
    args = parser.parse_args(["teach", "record", "--name", "auto capture"])
    assert args.command == "teach"
    assert args.teach_command == "record"


def test_parser_supports_teach_replay() -> None:
    parser = build_parser()
    args = parser.parse_args(["teach", "replay", "--session-id", "abc123", "--speed-factor", "2"])
    assert args.command == "teach"
    assert args.teach_command == "replay"
