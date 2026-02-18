from __future__ import annotations

import argparse
import logging

from task_automation_studio.config.settings import Settings
from task_automation_studio.utils.logging_config import configure_logging
from task_automation_studio.workflows.registry import list_available_workflows, load_workflow_from_source


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Task Automation Studio")
    parser.add_argument("--ui", action="store_true", help="Launch desktop UI.")

    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run a workflow against an Excel file.")
    workflow_group = run_parser.add_mutually_exclusive_group(required=True)
    workflow_group.add_argument("--workflow", choices=list_available_workflows(), help="Built-in workflow name.")
    workflow_group.add_argument("--workflow-file", help="Path to workflow JSON file.")
    run_parser.add_argument("--input-file", required=True, help="Input Excel file path.")
    run_parser.add_argument("--output-file", help="Output Excel file path for run results.")
    run_parser.add_argument("--report-file", help="JSON report output path.")
    run_parser.add_argument(
        "--safe-stop-error-rate",
        type=float,
        default=None,
        help="Stop when (failed + needs_review) / processed exceeds threshold [0..1].",
    )
    mode_group = run_parser.add_mutually_exclusive_group()
    mode_group.add_argument("--dry-run", dest="dry_run", action="store_true", help="Run without external side effects.")
    mode_group.add_argument("--live-run", dest="dry_run", action="store_false", help="Run with real connectors.")
    run_parser.set_defaults(dry_run=True)

    run_parser.add_argument("--email-host", default="", help="IMAP host for OTP retrieval.")
    run_parser.add_argument("--email-username", default="", help="Mailbox username.")
    run_parser.add_argument("--email-password", default="", help="Mailbox password.")
    run_parser.add_argument("--email-folder", default="INBOX", help="Mailbox folder.")
    return parser


def main() -> int:
    settings = Settings.from_env()
    configure_logging(settings.log_dir)
    logger = logging.getLogger("task_automation_studio")

    parser = build_parser()
    args = parser.parse_args()

    if args.ui or args.command == "ui":
        from task_automation_studio.ui.main_window import launch_ui

        return launch_ui()

    if args.command == "run":
        from task_automation_studio.services.executors import EmailRuntimeConfig
        from task_automation_studio.services.runner import AutomationRunner

        workflow = load_workflow_from_source(workflow_name=args.workflow, workflow_file=args.workflow_file)
        email_config = EmailRuntimeConfig(
            enabled=bool(args.email_host and args.email_username and args.email_password),
            host=args.email_host,
            username=args.email_username,
            password=args.email_password,
            folder=args.email_folder,
        )
        safe_stop_error_rate = (
            settings.default_safe_stop_error_rate
            if args.safe_stop_error_rate is None
            else max(0.0, min(1.0, args.safe_stop_error_rate))
        )

        runner = AutomationRunner(settings=settings)
        summary = runner.run_excel_workflow(
            workflow=workflow,
            input_file=args.input_file,
            output_file=args.output_file,
            report_file=args.report_file,
            dry_run=args.dry_run,
            safe_stop_error_rate=safe_stop_error_rate,
            email_config=email_config,
        )
        logger.info("Run completed: %s", summary.to_dict())
        print(summary.to_dict())
        return 0

    logger.info("No command provided. Use '--ui' or 'run'.")
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
