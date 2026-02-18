from __future__ import annotations

import logging
from collections.abc import Iterable

from task_automation_studio.core.enums import ExecutionStatus, RecordStatus
from task_automation_studio.core.interfaces import StepExecutor
from task_automation_studio.core.models import (
    RecordContext,
    RecordInput,
    RecordResult,
    StepDefinition,
    StepExecutionResult,
    WorkflowDefinition,
)


class WorkflowEngine:
    """Deterministic workflow executor with safe-stop behavior."""

    def __init__(self, executors: dict[str, StepExecutor], logger: logging.Logger | None = None) -> None:
        self._executors = executors
        self._logger = logger or logging.getLogger(__name__)

    def run_record(
        self,
        *,
        workflow: WorkflowDefinition,
        record: RecordInput,
        dry_run: bool = False,
    ) -> RecordResult:
        context = RecordContext(record=record)
        step_results: list[StepExecutionResult] = []

        for step in workflow.steps:
            pre_check = self._pre_check(step=step, context=context)
            if pre_check is not None:
                step_results.append(pre_check)
                return RecordResult(
                    record=record,
                    status=RecordStatus.NEEDS_REVIEW,
                    step_results=step_results,
                    error_code="PRECHECK_FAILED",
                    error_message=pre_check.message,
                )

            executor = self._executors.get(step.action)
            if executor is None:
                message = f"No executor registered for action '{step.action}'."
                step_results.append(
                    StepExecutionResult(
                        step_id=step.step_id,
                        status=ExecutionStatus.FAILED,
                        message=message,
                    )
                )
                return RecordResult(
                    record=record,
                    status=RecordStatus.NEEDS_REVIEW,
                    step_results=step_results,
                    error_code="MISSING_EXECUTOR",
                    error_message=message,
                )

            result = executor.execute(step=step, context=context, dry_run=dry_run)
            step_results.append(result)

            post_check = self._post_check(step=step, result=result)
            if post_check is not None:
                step_results.append(post_check)
                return RecordResult(
                    record=record,
                    status=RecordStatus.FAILED,
                    step_results=step_results,
                    error_code="POSTCHECK_FAILED",
                    error_message=post_check.message,
                )

            if result.status != ExecutionStatus.SUCCESS:
                return RecordResult(
                    record=record,
                    status=RecordStatus.FAILED,
                    step_results=step_results,
                    error_code="STEP_FAILED",
                    error_message=result.message or f"Step '{step.step_id}' failed.",
                )

        return RecordResult(record=record, status=RecordStatus.SUCCESS, step_results=step_results)

    def run_batch(
        self,
        *,
        workflow: WorkflowDefinition,
        records: Iterable[RecordInput],
        dry_run: bool = False,
        safe_stop_error_rate: float = 0.2,
    ) -> list[RecordResult]:
        results: list[RecordResult] = []
        failed_count = 0

        for index, record in enumerate(records, start=1):
            result = self.run_record(workflow=workflow, record=record, dry_run=dry_run)
            results.append(result)

            if result.status in {RecordStatus.FAILED, RecordStatus.NEEDS_REVIEW}:
                failed_count += 1

            error_rate = failed_count / index
            if error_rate > safe_stop_error_rate:
                self._logger.error(
                    "Safe stop triggered at record %s (error_rate=%.2f, threshold=%.2f).",
                    index,
                    error_rate,
                    safe_stop_error_rate,
                )
                break

        return results

    def _pre_check(self, *, step: StepDefinition, context: RecordContext) -> StepExecutionResult | None:
        missing_fields: list[str] = []
        for field_name in step.required_inputs:
            value = getattr(context.record, field_name, None)
            if value in (None, ""):
                missing_fields.append(field_name)

        if missing_fields:
            return StepExecutionResult(
                step_id=step.step_id,
                status=ExecutionStatus.FAILED,
                message=f"Missing required fields: {', '.join(missing_fields)}",
            )
        return None

    def _post_check(self, *, step: StepDefinition, result: StepExecutionResult) -> StepExecutionResult | None:
        if step.success_signals and not result.evidence:
            return StepExecutionResult(
                step_id=step.step_id,
                status=ExecutionStatus.FAILED,
                message="Step missing evidence while success signals are required.",
            )
        return None
