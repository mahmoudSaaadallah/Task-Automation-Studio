from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from task_automation_studio.core.models import StepDefinition, StepPolicy, WorkflowDefinition


STEP_TYPE_TO_ACTION = {
    "open_url": "browser.open_url",
    "fill_field": "browser.fill_field",
    "click": "browser.click",
    "wait_for": "browser.wait_for",
    "fetch_otp": "email.fetch_otp",
    "write_cell": "excel.write_cell",
    "mark_record_done": "record.mark_record_done",
}


def load_workflow_from_json(path: str | Path) -> WorkflowDefinition:
    payload = _read_json(path)

    steps_raw = payload.get("steps", [])
    if not isinstance(steps_raw, list) or not steps_raw:
        raise ValueError("Workflow JSON must contain a non-empty 'steps' array.")

    steps: list[StepDefinition] = []
    for idx, item in enumerate(steps_raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Step #{idx} must be an object.")
        steps.append(_build_step(item, idx))

    workflow_id = str(payload.get("workflow_id", "")).strip()
    name = str(payload.get("name", "")).strip()
    if not workflow_id or not name:
        raise ValueError("Workflow JSON requires non-empty 'workflow_id' and 'name'.")

    return WorkflowDefinition(workflow_id=workflow_id, name=name, steps=steps)


def _build_step(step_raw: dict[str, Any], index: int) -> StepDefinition:
    step_id = str(step_raw.get("id", "")).strip()
    if not step_id:
        raise ValueError(f"Step #{index} is missing required field 'id'.")

    action = _resolve_action(step_raw)
    params = step_raw.get("params", {})
    if not isinstance(params, dict):
        raise ValueError(f"Step '{step_id}' has invalid 'params'. Expected object.")

    required_inputs = step_raw.get("required_inputs", [])
    if not isinstance(required_inputs, list):
        raise ValueError(f"Step '{step_id}' has invalid 'required_inputs'. Expected array.")
    required_inputs = [str(v) for v in required_inputs]

    post_check = step_raw.get("post_check", {})
    success_signals = [f"post_check:{key}" for key in post_check.keys()] if isinstance(post_check, dict) else []

    retry = step_raw.get("retry", {})
    if not isinstance(retry, dict):
        retry = {}
    max_attempts = int(retry.get("max_attempts", 3))
    backoff_seconds = int(retry.get("backoff_seconds", 2))

    return StepDefinition(
        step_id=step_id,
        name=str(step_raw.get("name") or step_id).strip(),
        action=action,
        params=params,
        required_inputs=required_inputs,
        success_signals=success_signals,
        policy=StepPolicy(
            retry_count=max(0, max_attempts - 1),
            retry_backoff_seconds=max(1, backoff_seconds),
        ),
    )


def _resolve_action(step_raw: dict[str, Any]) -> str:
    action = step_raw.get("action")
    if isinstance(action, str) and action.strip():
        return action.strip()

    step_type = step_raw.get("type")
    if not isinstance(step_type, str) or not step_type.strip():
        raise ValueError("Each step must include either 'action' or 'type'.")

    mapped = STEP_TYPE_TO_ACTION.get(step_type.strip())
    if not mapped:
        raise ValueError(f"Unsupported step type '{step_type}'.")
    return mapped


def _read_json(path: str | Path) -> dict[str, Any]:
    workflow_path = Path(path)
    if not workflow_path.exists():
        raise FileNotFoundError(f"Workflow file not found: {workflow_path}")

    data = json.loads(workflow_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Workflow file root must be a JSON object.")
    return data
