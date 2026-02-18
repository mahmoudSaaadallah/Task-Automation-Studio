from __future__ import annotations

import json
from pathlib import Path

import pytest

from task_automation_studio.workflows.loader import load_workflow_from_json


def test_load_workflow_from_json_maps_step_types(tmp_path: Path) -> None:
    workflow_file = tmp_path / "workflow.json"
    payload = {
        "workflow_id": "wf_1",
        "name": "WF One",
        "steps": [
            {
                "id": "open_1",
                "type": "open_url",
                "params": {"url": "https://example.com"},
                "retry": {"max_attempts": 2, "backoff_seconds": 3},
            }
        ],
    }
    workflow_file.write_text(json.dumps(payload), encoding="utf-8")

    workflow = load_workflow_from_json(workflow_file)

    assert workflow.workflow_id == "wf_1"
    assert workflow.steps[0].action == "browser.open_url"
    assert workflow.steps[0].policy.retry_count == 1
    assert workflow.steps[0].policy.retry_backoff_seconds == 3


def test_load_workflow_from_json_rejects_unknown_type(tmp_path: Path) -> None:
    workflow_file = tmp_path / "bad_workflow.json"
    payload = {
        "workflow_id": "wf_bad",
        "name": "Bad",
        "steps": [{"id": "s1", "type": "not_supported", "params": {}}],
    }
    workflow_file.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported step type"):
        load_workflow_from_json(workflow_file)
