from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

from task_automation_studio.core.enums import ExecutionStatus, RecordStatus


EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class StepPolicy(BaseModel):
    timeout_seconds: int = Field(default=30, ge=1, le=600)
    retry_count: int = Field(default=2, ge=0, le=10)
    retry_backoff_seconds: int = Field(default=2, ge=1, le=60)


class StepDefinition(BaseModel):
    step_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    action: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    required_inputs: list[str] = Field(default_factory=list)
    success_signals: list[str] = Field(default_factory=list)
    policy: StepPolicy = Field(default_factory=StepPolicy)


class WorkflowDefinition(BaseModel):
    workflow_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    steps: list[StepDefinition] = Field(min_length=1)


class RecordInput(BaseModel):
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    email: str = Field(min_length=5)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if not EMAIL_REGEX.match(value):
            raise ValueError("Invalid email format.")
        return value.lower().strip()


class RecordContext(BaseModel):
    record: RecordInput
    metadata: dict[str, Any] = Field(default_factory=dict)


class StepExecutionResult(BaseModel):
    step_id: str
    status: ExecutionStatus
    message: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)
    attempt: int = 1


class RecordResult(BaseModel):
    record: RecordInput
    status: RecordStatus
    step_results: list[StepExecutionResult] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None


class JobConfig(BaseModel):
    workflow_id: str = Field(min_length=1)
    dry_run: bool = False
    safe_stop_error_rate: float = Field(default=0.2, ge=0.0, le=1.0)
