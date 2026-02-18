from __future__ import annotations

from typing import Protocol

from task_automation_studio.core.models import RecordContext, StepDefinition, StepExecutionResult


class StepExecutor(Protocol):
    def execute(
        self,
        *,
        step: StepDefinition,
        context: RecordContext,
        dry_run: bool = False,
    ) -> StepExecutionResult:
        ...
