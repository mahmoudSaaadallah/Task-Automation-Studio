from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from task_automation_studio.core.models import RecordResult
from task_automation_studio.persistence.models import JobRun, RecordRun


class JobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_job_run(self, workflow_id: str) -> JobRun:
        job = JobRun(workflow_id=workflow_id, status="running")
        self._session.add(job)
        self._session.commit()
        self._session.refresh(job)
        return job

    def add_record_result(self, job_run_id: int, result: RecordResult) -> RecordRun:
        record = RecordRun(
            job_run_id=job_run_id,
            email=result.record.email,
            status=result.status.value,
            error_code=result.error_code,
            error_message=result.error_message,
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def complete_job_run(self, job_run_id: int, status: str = "completed") -> None:
        job = self._session.get(JobRun, job_run_id)
        if job is None:
            return
        job.status = status
        job.completed_at = datetime.utcnow()
        self._session.commit()
