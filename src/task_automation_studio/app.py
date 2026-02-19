from __future__ import annotations

import argparse
import json
import logging

from task_automation_studio.config.settings import Settings
from task_automation_studio.core.teach_models import TeachEventType
from task_automation_studio.utils.logging_config import configure_logging
from task_automation_studio.workflows.loader import summarize_workflow
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

    teach_parser = subparsers.add_parser("teach", help="Manage teach sessions.")
    teach_sub = teach_parser.add_subparsers(dest="teach_command", required=True)

    teach_start = teach_sub.add_parser("start", help="Start a new teach session.")
    teach_start.add_argument("--name", required=True, help="Teach session name.")

    teach_record = teach_sub.add_parser("record", help="Auto-record global events until ESC is pressed.")
    teach_record.add_argument("--name", required=True, help="Teach session name.")
    teach_record.add_argument("--max-seconds", type=float, default=0.0, help="Optional timeout. 0 means wait until ESC.")

    teach_event = teach_sub.add_parser("event", help="Append one event to an active teach session.")
    teach_event.add_argument("--session-id", required=True, help="Teach session id.")
    teach_event.add_argument("--type", required=True, choices=[item.value for item in TeachEventType], help="Event type.")
    teach_event.add_argument("--payload", default="{}", help="Event payload as JSON object string.")
    teach_event.add_argument(
        "--set",
        dest="payload_pairs",
        action="append",
        default=[],
        help="Event payload entry in key=value format (can be repeated).",
    )
    teach_event.add_argument("--sensitive", action="store_true", help="Mark event as sensitive.")

    teach_checkpoint = teach_sub.add_parser("checkpoint", help="Add a checkpoint event.")
    teach_checkpoint.add_argument("--session-id", required=True, help="Teach session id.")
    teach_checkpoint.add_argument("--name", required=True, help="Checkpoint name.")

    teach_finish = teach_sub.add_parser("finish", help="Finish an active teach session.")
    teach_finish.add_argument("--session-id", required=True, help="Teach session id.")

    teach_export = teach_sub.add_parser("export", help="Export teach session as JSON.")
    teach_export.add_argument("--session-id", required=True, help="Teach session id.")
    teach_export.add_argument("--output-file", required=True, help="Output JSON path.")

    teach_compile = teach_sub.add_parser("compile", help="Compile teach session into workflow JSON.")
    teach_compile.add_argument("--session-id", required=True, help="Teach session id.")
    teach_compile.add_argument("--workflow-id", required=True, help="Output workflow id.")
    teach_compile.add_argument("--output-file", required=True, help="Output workflow JSON path.")

    teach_replay = teach_sub.add_parser("replay", help="Replay recorded global events from a teach session.")
    teach_replay.add_argument("--session-id", required=True, help="Teach session id.")
    teach_replay.add_argument("--speed-factor", type=float, default=1.0, help="Replay speed multiplier (1.0 normal).")
    teach_replay.add_argument("--repeat-count", type=int, default=1, help="Number of times to replay the session.")
    teach_replay.add_argument("--diagnostics-file", default="", help="Optional replay diagnostics JSON path.")

    teach_sub.add_parser("list", help="List teach sessions.")

    workflow_parser = subparsers.add_parser("workflow", help="Workflow utility commands.")
    workflow_sub = workflow_parser.add_subparsers(dest="workflow_command", required=True)
    workflow_validate = workflow_sub.add_parser("validate", help="Validate workflow JSON and print summary.")
    workflow_validate.add_argument("--workflow-file", required=True, help="Path to workflow JSON file.")
    return parser


def main() -> int:
    settings = Settings.from_env()
    configure_logging(settings.log_dir)
    logger = logging.getLogger("task_automation_studio")

    parser = build_parser()
    args = parser.parse_args()

    if args.ui or args.command == "ui":
        from task_automation_studio.ui.main_window import launch_ui

        return launch_ui(settings=settings)

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

    if args.command == "teach":
        from task_automation_studio.services.teach_sessions import TeachSessionService

        service = TeachSessionService(settings=settings)

        if args.teach_command == "start":
            session = service.start_session(name=args.name)
            print(session.model_dump(mode="json"))
            return 0

        if args.teach_command == "record":
            from task_automation_studio.services.auto_recorder import AutoTeachRecorder

            session = service.start_session(name=args.name)
            recorder = AutoTeachRecorder(session_service=service)
            recorder.start(session_id=session.session_id)
            print(
                {
                    "session_id": session.session_id,
                    "status": "recording",
                    "message": "Recording started. Press ESC to stop.",
                }
            )
            try:
                timeout = args.max_seconds if args.max_seconds > 0 else None
                recorder.wait_until_stopped(timeout=timeout)
                if recorder.is_recording:
                    recorder.stop(finish_session=True)
            except KeyboardInterrupt:
                if recorder.is_recording:
                    recorder.stop(finish_session=True)
            final_session = service.get_session(session_id=session.session_id)
            print(final_session.model_dump(mode="json"))
            return 0

        if args.teach_command == "event":
            try:
                payload = _parse_payload_json(args.payload)
                payload.update(_parse_payload_pairs(args.payload_pairs))
            except ValueError as exc:
                logger.error(str(exc))
                return 2
            session = service.add_event(
                session_id=args.session_id,
                event_type=TeachEventType(args.type),
                payload=payload,
                sensitive=args.sensitive,
            )
            print(session.model_dump(mode="json"))
            return 0

        if args.teach_command == "checkpoint":
            session = service.add_event(
                session_id=args.session_id,
                event_type=TeachEventType.CHECKPOINT,
                payload={"name": args.name},
                sensitive=False,
            )
            print(session.model_dump(mode="json"))
            return 0

        if args.teach_command == "finish":
            session = service.finish_session(session_id=args.session_id)
            print(session.model_dump(mode="json"))
            return 0

        if args.teach_command == "export":
            output = service.export_session(session_id=args.session_id, output_file=args.output_file)
            print({"session_id": args.session_id, "output_file": str(output)})
            return 0

        if args.teach_command == "compile":
            from task_automation_studio.services.session_compiler import TeachSessionCompiler

            compiler = TeachSessionCompiler(session_service=service)
            output = compiler.compile_to_workflow(
                session_id=args.session_id,
                workflow_id=args.workflow_id,
                output_file=args.output_file,
            )
            print({"session_id": args.session_id, "workflow_id": args.workflow_id, "output_file": str(output)})
            return 0

        if args.teach_command == "replay":
            from task_automation_studio.services.session_replay import TeachSessionReplayer

            replayer = TeachSessionReplayer(session_service=service)
            summary = replayer.replay(
                session_id=args.session_id,
                speed_factor=args.speed_factor,
                repeat_count=args.repeat_count,
                diagnostics_output_file=args.diagnostics_file.strip() or None,
                save_diagnostics=True,
            )
            print(summary.to_dict())
            return 0

        if args.teach_command == "list":
            sessions = service.list_sessions()
            print([session.model_dump(mode="json") for session in sessions])
            return 0

    if args.command == "workflow":
        if args.workflow_command == "validate":
            try:
                summary = summarize_workflow(args.workflow_file)
            except Exception as exc:
                logger.error("Workflow validation failed: %s", exc)
                return 2
            print(summary)
            return 0

    logger.info("No command provided. Use '--ui' or 'run'.")
    parser.print_help()
    return 1


def _parse_payload_json(payload: str) -> dict[str, object]:
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid payload JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("Payload JSON must be an object.")
    return value


def _parse_payload_pairs(pairs: list[str]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"Invalid --set value '{pair}'. Expected key=value.")
        key, value = pair.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("Payload key in --set cannot be empty.")
        payload[key] = value
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
