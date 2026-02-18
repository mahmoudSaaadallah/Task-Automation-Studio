from __future__ import annotations

import json
from pathlib import Path

from task_automation_studio.config.settings import Settings
from task_automation_studio.core.teach_models import TeachEventType
from task_automation_studio.services.session_compiler import TeachSessionCompiler
from task_automation_studio.services.teach_sessions import TeachSessionService
from task_automation_studio.workflows.loader import load_workflow_from_json


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'app.db'}",
        log_dir=tmp_path / "logs",
        artifacts_dir=tmp_path / "artifacts",
    )


def test_compile_teach_session_to_workflow(tmp_path: Path) -> None:
    service = TeachSessionService(settings=_settings(tmp_path))
    session = service.start_session(name="Compile demo")
    service.add_event(
        session_id=session.session_id,
        event_type=TeachEventType.OPEN_URL,
        payload={"url": "https://zoom.us/signup"},
    )
    service.add_event(
        session_id=session.session_id,
        event_type=TeachEventType.FILL,
        payload={"selector": "input[name='email']", "value": "{{record.email}}"},
    )
    service.finish_session(session_id=session.session_id)

    compiler = TeachSessionCompiler(session_service=service)
    output_file = tmp_path / "compiled.workflow.json"
    compiler.compile_to_workflow(
        session_id=session.session_id,
        workflow_id="compiled_zoom_demo",
        output_file=output_file,
    )

    assert output_file.exists()
    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["workflow_id"] == "compiled_zoom_demo"
    assert len(payload["steps"]) == 2

    workflow = load_workflow_from_json(output_file)
    assert workflow.workflow_id == "compiled_zoom_demo"
    assert workflow.steps[1].required_inputs == ["email"]
