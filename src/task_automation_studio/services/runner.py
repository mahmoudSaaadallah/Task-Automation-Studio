from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from task_automation_studio.config.settings import Settings
from task_automation_studio.connectors.browser_connector import PlaywrightBrowserConnector
from task_automation_studio.connectors.excel_connector import ExcelConnector
from task_automation_studio.core.engine import WorkflowEngine
from task_automation_studio.core.enums import RecordStatus
from task_automation_studio.core.models import RecordInput, RecordResult, WorkflowDefinition
from task_automation_studio.persistence.database import init_database
from task_automation_studio.persistence.repository import JobRepository
from task_automation_studio.services.executors import EmailRuntimeConfig, build_executors_for_workflow


@dataclass(slots=True)
class RunSummary:
    workflow_id: str
    job_run_id: int
    total_records: int
    processed_records: int
    unprocessed_records: int
    duplicate_skipped: int
    success_count: int
    failed_count: int
    needs_review_count: int
    skipped_count: int
    safe_stopped: bool
    output_file: str
    report_file: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class AutomationRunner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._excel = ExcelConnector()
        self._session_factory = init_database(settings.database_url)

    def run_excel_workflow(
        self,
        *,
        workflow: WorkflowDefinition,
        input_file: str | Path,
        output_file: str | Path | None,
        report_file: str | Path | None,
        dry_run: bool,
        safe_stop_error_rate: float,
        email_config: EmailRuntimeConfig,
    ) -> RunSummary:
        records = self._excel.read_records(input_file)
        browser_connector = PlaywrightBrowserConnector(headless=True)
        self._register_default_browser_handlers(browser_connector=browser_connector)

        actions = sorted({step.action for step in workflow.steps})
        engine = WorkflowEngine(
            executors=build_executors_for_workflow(
                actions=actions,
                email_config=email_config,
                browser_connector=browser_connector,
            )
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(output_file) if output_file else self._settings.artifacts_dir / f"{workflow.workflow_id}_{timestamp}.xlsx"
        report_path = Path(report_file) if report_file else self._settings.artifacts_dir / f"{workflow.workflow_id}_{timestamp}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.parent.mkdir(parents=True, exist_ok=True)

        results: list[RecordResult] = []
        seen_emails: set[str] = set()
        duplicate_count = 0
        processed_non_skipped = 0
        failed_or_review = 0
        safe_stopped = False
        job_run_id = 0

        with self._session_factory() as session:
            repo = JobRepository(session)
            job = repo.create_job_run(workflow.workflow_id)
            job_run_id = job.id

            for record in records:
                if record.email in seen_emails:
                    duplicate_count += 1
                    result = self._build_duplicate_result(record)
                else:
                    seen_emails.add(record.email)
                    result = engine.run_record(workflow=workflow, record=record, dry_run=dry_run)

                    processed_non_skipped += 1
                    if result.status in {RecordStatus.FAILED, RecordStatus.NEEDS_REVIEW}:
                        failed_or_review += 1

                    if processed_non_skipped > 0:
                        error_rate = failed_or_review / processed_non_skipped
                        if error_rate > safe_stop_error_rate:
                            safe_stopped = True

                repo.add_record_result(job.id, result)
                results.append(result)

                if safe_stopped:
                    break

            repo.complete_job_run(job.id, status="safe_stopped" if safe_stopped else "completed")

        self._excel.write_results(output_path, results)
        summary = self._build_summary(
            workflow_id=workflow.workflow_id,
            job_run_id=job_run_id,
            total_records=len(records),
            duplicate_skipped=duplicate_count,
            safe_stopped=safe_stopped,
            results=results,
            output_file=output_path,
            report_file=report_path,
        )
        self._write_report(report_path, summary)
        return summary

    def _register_default_browser_handlers(self, *, browser_connector: PlaywrightBrowserConnector) -> None:
        def _not_implemented_handler(payload: dict[str, object]) -> dict[str, object]:
            record = payload.get("record", {})
            if not isinstance(record, dict):
                record = {}
            return {
                "verified": False,
                "message": "Live browser handler not implemented for this action yet.",
                "record_email": record.get("email", ""),
            }

        browser_connector.register_action_handler("browser.open_signup", _not_implemented_handler)
        browser_connector.register_action_handler("browser.fill_signup_form", _not_implemented_handler)
        browser_connector.register_action_handler("browser.submit_signup", _not_implemented_handler)
        browser_connector.register_action_handler("browser.confirm_otp", _not_implemented_handler)

    def _build_duplicate_result(self, record: RecordInput) -> RecordResult:
        return RecordResult(
            record=record,
            status=RecordStatus.SKIPPED,
            error_code="DUPLICATE_EMAIL",
            error_message="Email already processed in current run.",
        )

    def _build_summary(
        self,
        *,
        workflow_id: str,
        job_run_id: int,
        total_records: int,
        duplicate_skipped: int,
        safe_stopped: bool,
        results: list[RecordResult],
        output_file: Path,
        report_file: Path,
    ) -> RunSummary:
        success_count = sum(1 for r in results if r.status == RecordStatus.SUCCESS)
        failed_count = sum(1 for r in results if r.status == RecordStatus.FAILED)
        needs_review_count = sum(1 for r in results if r.status == RecordStatus.NEEDS_REVIEW)
        skipped_count = sum(1 for r in results if r.status == RecordStatus.SKIPPED)

        return RunSummary(
            workflow_id=workflow_id,
            job_run_id=job_run_id,
            total_records=total_records,
            processed_records=len(results),
            unprocessed_records=max(0, total_records - len(results)),
            duplicate_skipped=duplicate_skipped,
            success_count=success_count,
            failed_count=failed_count,
            needs_review_count=needs_review_count,
            skipped_count=skipped_count,
            safe_stopped=safe_stopped,
            output_file=str(output_file),
            report_file=str(report_file),
        )

    def _write_report(self, report_path: Path, summary: RunSummary) -> None:
        report_path.write_text(json.dumps(summary.to_dict(), indent=2), encoding="utf-8")
