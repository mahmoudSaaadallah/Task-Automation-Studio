from __future__ import annotations

from pathlib import Path

from task_automation_studio.connectors.excel_connector import ExcelConnector
from task_automation_studio.core.engine import WorkflowEngine
from task_automation_studio.core.models import RecordResult, WorkflowDefinition


class JobOrchestrator:
    def __init__(self, engine: WorkflowEngine, excel_connector: ExcelConnector) -> None:
        self._engine = engine
        self._excel = excel_connector

    def run_from_excel(
        self,
        *,
        workflow: WorkflowDefinition,
        input_file: str | Path,
        output_file: str | Path | None = None,
        dry_run: bool = False,
        safe_stop_error_rate: float = 0.2,
    ) -> list[RecordResult]:
        records = self._excel.read_records(input_file)
        results = self._engine.run_batch(
            workflow=workflow,
            records=records,
            dry_run=dry_run,
            safe_stop_error_rate=safe_stop_error_rate,
        )
        if output_file is not None:
            self._excel.write_results(output_file, results)
        return results
