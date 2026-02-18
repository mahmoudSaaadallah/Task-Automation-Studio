from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from task_automation_studio.config.settings import Settings
from task_automation_studio.core.teach_models import TeachEventData, TeachEventType, TeachSessionData
from task_automation_studio.persistence.database import init_database
from task_automation_studio.persistence.teach_repository import TeachSessionRepository


class TeachSessionService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._session_factory = init_database(settings.database_url)

    def start_session(self, *, name: str) -> TeachSessionData:
        session_id = uuid4().hex
        with self._session_factory() as session:
            repo = TeachSessionRepository(session)
            repo.create_session(session_id=session_id, name=name)
            return repo.to_data(session_id)

    def list_sessions(self) -> list[TeachSessionData]:
        with self._session_factory() as session:
            repo = TeachSessionRepository(session)
            sessions = repo.list_sessions()
            return [repo.to_data(item.session_id) for item in sessions]

    def add_event(
        self,
        *,
        session_id: str,
        event_type: TeachEventType,
        payload: dict[str, object] | None = None,
        sensitive: bool = False,
        event_id: str | None = None,
    ) -> TeachSessionData:
        payload = payload or {}
        event = TeachEventData(
            event_id=event_id or uuid4().hex,
            event_type=event_type,
            payload=payload,
            sensitive=sensitive,
            timestamp=datetime.now(timezone.utc),
        )

        with self._session_factory() as session:
            repo = TeachSessionRepository(session)
            repo.add_event(session_id=session_id, event=event)
            return repo.to_data(session_id)

    def finish_session(self, *, session_id: str) -> TeachSessionData:
        with self._session_factory() as session:
            repo = TeachSessionRepository(session)
            repo.finish_session(session_id)
            return repo.to_data(session_id)

    def export_session(self, *, session_id: str, output_file: str | Path) -> Path:
        with self._session_factory() as session:
            repo = TeachSessionRepository(session)
            data = repo.to_data(session_id)

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(data.model_dump(mode="json"), indent=2), encoding="utf-8")
        return output_path
