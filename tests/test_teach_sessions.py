from __future__ import annotations

import json
from pathlib import Path

from task_automation_studio.config.settings import Settings
from task_automation_studio.core.teach_models import TeachEventType, TeachSessionStatus
from task_automation_studio.services.teach_sessions import TeachSessionService


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'app.db'}",
        log_dir=tmp_path / "logs",
        artifacts_dir=tmp_path / "artifacts",
    )


def test_teach_session_lifecycle(tmp_path: Path) -> None:
    service = TeachSessionService(settings=_settings(tmp_path))

    session = service.start_session(name="Zoom onboarding")
    assert session.status == TeachSessionStatus.RECORDING
    assert session.events == []

    updated = service.add_event(
        session_id=session.session_id,
        event_type=TeachEventType.OPEN_URL,
        payload={"url": "https://zoom.us/signup"},
    )
    assert len(updated.events) == 1
    assert updated.events[0].payload["url"] == "https://zoom.us/signup"

    finished = service.finish_session(session_id=session.session_id)
    assert finished.status == TeachSessionStatus.FINISHED


def test_teach_session_export(tmp_path: Path) -> None:
    service = TeachSessionService(settings=_settings(tmp_path))
    session = service.start_session(name="Export me")
    service.add_event(
        session_id=session.session_id,
        event_type=TeachEventType.CHECKPOINT,
        payload={"name": "submitted"},
    )
    service.finish_session(session_id=session.session_id)

    output = service.export_session(session_id=session.session_id, output_file=tmp_path / "exports" / "session.json")
    assert output.exists()

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["session_id"] == session.session_id
    assert payload["events"][0]["event_type"] == TeachEventType.CHECKPOINT
