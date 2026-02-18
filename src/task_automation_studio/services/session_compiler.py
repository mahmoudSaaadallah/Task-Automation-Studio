from __future__ import annotations

import json
from pathlib import Path

from task_automation_studio.core.teach_models import TeachEventData, TeachEventType, TeachSessionData
from task_automation_studio.services.teach_sessions import TeachSessionService


EVENT_TO_STEP_TYPE: dict[TeachEventType, str] = {
    TeachEventType.OPEN_URL: "open_url",
    TeachEventType.CLICK: "click",
    TeachEventType.FILL: "fill_field",
    TeachEventType.WAIT_FOR: "wait_for",
    TeachEventType.CHECKPOINT: "wait_for",
}


class TeachSessionCompiler:
    def __init__(self, session_service: TeachSessionService) -> None:
        self._session_service = session_service

    def compile_to_workflow(
        self,
        *,
        session_id: str,
        workflow_id: str,
        output_file: str | Path,
    ) -> Path:
        session = self._session_service.get_session(session_id=session_id)
        workflow = self._build_workflow_payload(session=session, workflow_id=workflow_id)

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(workflow, indent=2), encoding="utf-8")
        return output_path

    def _build_workflow_payload(self, *, session: TeachSessionData, workflow_id: str) -> dict[str, object]:
        steps: list[dict[str, object]] = []
        for idx, event in enumerate(session.events, start=1):
            step = self._event_to_step(event=event, index=idx)
            if step is not None:
                steps.append(step)

        if not steps:
            raise ValueError("Teach session contains no compilable events.")

        return {
            "workflow_id": workflow_id,
            "name": f"Compiled - {session.name}",
            "version": "1.0.0",
            "mode": "browser_first",
            "bindings": {
                "first_name": "{{record.first_name}}",
                "last_name": "{{record.last_name}}",
                "email": "{{record.email}}",
            },
            "steps": steps,
        }

    def _event_to_step(self, *, event: TeachEventData, index: int) -> dict[str, object] | None:
        if event.event_type in {TeachEventType.CLIPBOARD_COPY, TeachEventType.CLIPBOARD_PASTE, TeachEventType.WINDOW_SWITCH}:
            return None

        step_type = EVENT_TO_STEP_TYPE.get(event.event_type)
        if step_type is None:
            return None

        post_check = {}
        if event.event_type == TeachEventType.CHECKPOINT:
            post_check = {"checkpoint": str(event.payload.get("name", "checkpoint"))}

        required_inputs = self._infer_required_inputs(event)
        return {
            "id": f"step_{index:03d}",
            "type": step_type,
            "params": event.payload,
            "required_inputs": required_inputs,
            "retry": {"max_attempts": 3, "backoff_seconds": 2},
            "on_failure": "needs_review",
            "post_check": post_check,
        }

    def _infer_required_inputs(self, event: TeachEventData) -> list[str]:
        values = [str(v) for v in event.payload.values() if isinstance(v, (str, int, float, bool))]
        required: set[str] = set()
        for value in values:
            if "{{record.email}}" in value:
                required.add("email")
            if "{{record.first_name}}" in value:
                required.add("first_name")
            if "{{record.last_name}}" in value:
                required.add("last_name")
        return sorted(required)
