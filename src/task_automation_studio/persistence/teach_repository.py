from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from task_automation_studio.core.teach_models import TeachEventData, TeachSessionData, TeachSessionStatus
from task_automation_studio.persistence.models import TeachEvent, TeachSession


class TeachSessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_session(self, session_id: str, name: str) -> TeachSession:
        model = TeachSession(session_id=session_id, name=name, status=TeachSessionStatus.RECORDING.value)
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return model

    def list_sessions(self) -> list[TeachSession]:
        stmt = select(TeachSession).order_by(TeachSession.created_at.desc())
        return list(self._session.scalars(stmt).all())

    def get_by_session_id(self, session_id: str) -> TeachSession | None:
        stmt = select(TeachSession).where(TeachSession.session_id == session_id)
        return self._session.scalars(stmt).first()

    def add_event(self, *, session_id: str, event: TeachEventData) -> TeachEvent:
        session = self.get_by_session_id(session_id)
        if session is None:
            raise ValueError(f"Teach session '{session_id}' not found.")
        if session.status != TeachSessionStatus.RECORDING.value:
            raise ValueError(f"Teach session '{session_id}' is not in recording state.")

        model = TeachEvent(
            teach_session_id=session.id,
            event_id=event.event_id,
            event_type=event.event_type.value,
            payload_json=json.dumps(event.payload),
            sensitive=event.sensitive,
            created_at=event.timestamp,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return model

    def finish_session(self, session_id: str) -> TeachSession:
        session = self.get_by_session_id(session_id)
        if session is None:
            raise ValueError(f"Teach session '{session_id}' not found.")
        session.status = TeachSessionStatus.FINISHED.value
        session.finished_at = datetime.now()
        self._session.commit()
        self._session.refresh(session)
        return session

    def to_data(self, session_id: str) -> TeachSessionData:
        session = self.get_by_session_id(session_id)
        if session is None:
            raise ValueError(f"Teach session '{session_id}' not found.")

        stmt = select(TeachEvent).where(TeachEvent.teach_session_id == session.id).order_by(TeachEvent.created_at.asc())
        events = self._session.scalars(stmt).all()
        event_data = [
            TeachEventData(
                event_id=event.event_id,
                event_type=event.event_type,
                payload=json.loads(event.payload_json),
                sensitive=event.sensitive,
                timestamp=event.created_at,
            )
            for event in events
        ]
        return TeachSessionData(
            session_id=session.session_id,
            name=session.name,
            status=session.status,
            started_at=session.created_at,
            finished_at=session.finished_at,
            events=event_data,
        )
