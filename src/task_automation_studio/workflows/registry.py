from __future__ import annotations

from pathlib import Path

from task_automation_studio.core.models import WorkflowDefinition
from task_automation_studio.workflows.loader import load_workflow_from_json
from task_automation_studio.workflows.templates.zoom_signup import build_zoom_signup_workflow


def list_available_workflows() -> list[str]:
    return ["zoom_signup"]


def load_workflow(workflow_name: str) -> WorkflowDefinition:
    normalized = workflow_name.strip().lower()
    if normalized == "zoom_signup":
        return build_zoom_signup_workflow()
    raise ValueError(f"Unsupported workflow '{workflow_name}'. Available: {', '.join(list_available_workflows())}")


def load_workflow_from_source(*, workflow_name: str | None = None, workflow_file: str | Path | None = None) -> WorkflowDefinition:
    if workflow_file:
        return load_workflow_from_json(workflow_file)
    if workflow_name:
        return load_workflow(workflow_name)
    raise ValueError("Either workflow_name or workflow_file must be provided.")
