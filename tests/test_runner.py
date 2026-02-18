from __future__ import annotations

from pathlib import Path

import pandas as pd

from task_automation_studio.config.settings import Settings
from task_automation_studio.core.engine import WorkflowEngine
from task_automation_studio.core.enums import ExecutionStatus, RecordStatus
from task_automation_studio.core.models import (
    RecordContext,
    RecordInput,
    StepDefinition,
    StepExecutionResult,
    StepPolicy,
    WorkflowDefinition,
)
from task_automation_studio.services.executors import EmailRuntimeConfig
from task_automation_studio.services.runner import AutomationRunner
from task_automation_studio.workflows.registry import load_workflow


class FlakyExecutor:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, *, step: StepDefinition, context: RecordContext, dry_run: bool = False) -> StepExecutionResult:
        del context, dry_run
        self.calls += 1
        if self.calls == 1:
            return StepExecutionResult(step_id=step.step_id, status=ExecutionStatus.FAILED, message="try again")
        return StepExecutionResult(
            step_id=step.step_id,
            status=ExecutionStatus.SUCCESS,
            message="ok",
            evidence={"done": True},
        )


def _build_settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'app.db'}",
        log_dir=tmp_path / "logs",
        artifacts_dir=tmp_path / "artifacts",
    )


def _write_input_excel(path: Path) -> None:
    df = pd.DataFrame(
        [
            {"first_name": "A", "last_name": "B", "email": "a@example.com"},
            {"first_name": "C", "last_name": "D", "email": "a@example.com"},
            {"first_name": "E", "last_name": "F", "email": "e@example.com"},
        ]
    )
    df.to_excel(path, index=False)


def test_engine_retries_and_succeeds() -> None:
    workflow = WorkflowDefinition(
        workflow_id="retry_wf",
        name="retry",
        steps=[
            StepDefinition(
                step_id="step1",
                name="step1",
                action="flaky",
                policy=StepPolicy(retry_count=1, retry_backoff_seconds=1),
                success_signals=["done"],
            )
        ],
    )
    record = RecordInput(first_name="A", last_name="B", email="a@example.com")
    executor = FlakyExecutor()
    engine = WorkflowEngine(executors={"flaky": executor}, sleep_fn=lambda _: None)

    result = engine.run_record(workflow=workflow, record=record, dry_run=False)

    assert result.status == RecordStatus.SUCCESS
    assert executor.calls == 2
    assert result.step_results[0].attempt == 2


def test_runner_deduplicates_email_in_same_run(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    runner = AutomationRunner(settings=settings)
    workflow = load_workflow("zoom_signup")
    input_file = tmp_path / "employees.xlsx"
    _write_input_excel(input_file)

    summary = runner.run_excel_workflow(
        workflow=workflow,
        input_file=input_file,
        output_file=None,
        report_file=None,
        dry_run=True,
        safe_stop_error_rate=1.0,
        email_config=EmailRuntimeConfig(enabled=False),
    )

    assert summary.total_records == 3
    assert summary.duplicate_skipped == 1
    assert summary.success_count == 2
    assert summary.skipped_count == 1
    assert summary.safe_stopped is False
    assert Path(summary.output_file).exists()
    assert Path(summary.report_file).exists()


def test_runner_safe_stop_on_high_error_rate(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    runner = AutomationRunner(settings=settings)
    workflow = load_workflow("zoom_signup")
    input_file = tmp_path / "employees.xlsx"
    _write_input_excel(input_file)

    summary = runner.run_excel_workflow(
        workflow=workflow,
        input_file=input_file,
        output_file=None,
        report_file=None,
        dry_run=False,
        safe_stop_error_rate=0.2,
        email_config=EmailRuntimeConfig(enabled=False),
    )

    assert summary.safe_stopped is True
    assert summary.processed_records == 1
    assert summary.failed_count == 1
    assert summary.unprocessed_records == 2
