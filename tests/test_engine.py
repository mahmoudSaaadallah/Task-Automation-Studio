from task_automation_studio.core.engine import WorkflowEngine
from task_automation_studio.core.enums import ExecutionStatus, RecordStatus
from task_automation_studio.core.models import (
    RecordContext,
    RecordInput,
    StepDefinition,
    StepExecutionResult,
    WorkflowDefinition,
)


class DummyExecutor:
    def execute(self, *, step: StepDefinition, context: RecordContext, dry_run: bool = False) -> StepExecutionResult:
        return StepExecutionResult(
            step_id=step.step_id,
            status=ExecutionStatus.SUCCESS,
            message="ok",
            evidence={"signal": "ok"},
        )


def test_engine_runs_happy_path() -> None:
    workflow = WorkflowDefinition(
        workflow_id="w1",
        name="test",
        steps=[
            StepDefinition(
                step_id="s1",
                name="step",
                action="dummy",
                required_inputs=["first_name", "last_name", "email"],
                success_signals=["ok"],
            )
        ],
    )
    record = RecordInput(first_name="A", last_name="B", email="a@example.com")
    engine = WorkflowEngine(executors={"dummy": DummyExecutor()})

    result = engine.run_record(workflow=workflow, record=record, dry_run=True)

    assert result.status == RecordStatus.SUCCESS
    assert len(result.step_results) == 1
