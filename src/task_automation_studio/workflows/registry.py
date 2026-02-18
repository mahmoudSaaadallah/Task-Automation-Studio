from __future__ import annotations

from task_automation_studio.core.models import WorkflowDefinition
from task_automation_studio.workflows.templates.zoom_signup import build_zoom_signup_workflow


def list_available_workflows() -> list[str]:
    return ["zoom_signup"]


def load_workflow(workflow_name: str) -> WorkflowDefinition:
    normalized = workflow_name.strip().lower()
    if normalized == "zoom_signup":
        return build_zoom_signup_workflow()
    raise ValueError(f"Unsupported workflow '{workflow_name}'. Available: {', '.join(list_available_workflows())}")
