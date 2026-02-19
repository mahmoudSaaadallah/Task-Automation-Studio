from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from task_automation_studio.config.settings import Settings
from task_automation_studio.core.teach_models import TeachEventType
from task_automation_studio.services.auto_recorder import AutoTeachRecorder
from task_automation_studio.services.executors import EmailRuntimeConfig
from task_automation_studio.services.runner import AutomationRunner
from task_automation_studio.services.session_compiler import TeachSessionCompiler
from task_automation_studio.services.session_replay import TeachSessionReplayer
from task_automation_studio.services.teach_sessions import TeachSessionService
from task_automation_studio.workflows.loader import summarize_workflow
from task_automation_studio.workflows.registry import list_available_workflows, load_workflow_from_source


class RunWorkflowTab(QWidget):
    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        workflow_group = QGroupBox("Workflow Source")
        workflow_form = QFormLayout(workflow_group)

        self.workflow_combo = QComboBox()
        self.workflow_combo.addItems(list_available_workflows())
        workflow_form.addRow("Built-in workflow", self.workflow_combo)

        self.workflow_file_input = QLineEdit()
        self.workflow_file_input.setPlaceholderText("Optional: use workflow JSON file instead of built-in workflow")
        self.workflow_file_button = QPushButton("Browse...")
        self.workflow_file_button.clicked.connect(self._browse_workflow_file)
        workflow_file_row = QWidget()
        workflow_file_layout = QHBoxLayout(workflow_file_row)
        workflow_file_layout.setContentsMargins(0, 0, 0, 0)
        workflow_file_layout.addWidget(self.workflow_file_input)
        workflow_file_layout.addWidget(self.workflow_file_button)
        workflow_form.addRow("Workflow file", workflow_file_row)
        layout.addWidget(workflow_group)

        io_group = QGroupBox("Input and Output")
        io_form = QFormLayout(io_group)

        self.input_file_input = QLineEdit()
        self.input_file_button = QPushButton("Browse...")
        self.input_file_button.clicked.connect(self._browse_input_file)
        input_row = QWidget()
        input_layout = QHBoxLayout(input_row)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.addWidget(self.input_file_input)
        input_layout.addWidget(self.input_file_button)
        io_form.addRow("Input Excel", input_row)

        self.output_file_input = QLineEdit()
        self.output_file_input.setPlaceholderText("Optional: custom output Excel path")
        self.output_file_button = QPushButton("Browse...")
        self.output_file_button.clicked.connect(self._browse_output_file)
        output_row = QWidget()
        output_layout = QHBoxLayout(output_row)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.addWidget(self.output_file_input)
        output_layout.addWidget(self.output_file_button)
        io_form.addRow("Output Excel", output_row)

        self.report_file_input = QLineEdit()
        self.report_file_input.setPlaceholderText("Optional: custom JSON report path")
        self.report_file_button = QPushButton("Browse...")
        self.report_file_button.clicked.connect(self._browse_report_file)
        report_row = QWidget()
        report_layout = QHBoxLayout(report_row)
        report_layout.setContentsMargins(0, 0, 0, 0)
        report_layout.addWidget(self.report_file_input)
        report_layout.addWidget(self.report_file_button)
        io_form.addRow("Report JSON", report_row)

        layout.addWidget(io_group)

        options_group = QGroupBox("Run Options")
        options_form = QFormLayout(options_group)
        self.dry_run_checkbox = QCheckBox("Dry run (recommended)")
        self.dry_run_checkbox.setChecked(True)
        options_form.addRow("Mode", self.dry_run_checkbox)

        self.safe_stop_input = QDoubleSpinBox()
        self.safe_stop_input.setRange(0.0, 1.0)
        self.safe_stop_input.setSingleStep(0.05)
        self.safe_stop_input.setValue(self._settings.default_safe_stop_error_rate)
        options_form.addRow("Safe-stop error rate", self.safe_stop_input)
        layout.addWidget(options_group)

        email_group = QGroupBox("Email Connector (used only in live run)")
        email_form = QFormLayout(email_group)
        self.email_host_input = QLineEdit()
        self.email_username_input = QLineEdit()
        self.email_password_input = QLineEdit()
        self.email_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.email_folder_input = QLineEdit("INBOX")
        email_form.addRow("IMAP host", self.email_host_input)
        email_form.addRow("Username", self.email_username_input)
        email_form.addRow("Password", self.email_password_input)
        email_form.addRow("Folder", self.email_folder_input)
        layout.addWidget(email_group)

        self.run_button = QPushButton("Run Workflow")
        self.run_button.clicked.connect(self._run_workflow)
        layout.addWidget(self.run_button)

        self.result_output = QTextEdit()
        self.result_output.setReadOnly(True)
        self.result_output.setPlaceholderText("Run summary will appear here.")
        layout.addWidget(self.result_output)

    def _browse_workflow_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select workflow JSON", "", "JSON Files (*.json);;All Files (*)")
        if path:
            self.workflow_file_input.setText(path)

    def _browse_input_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select input Excel", "", "Excel Files (*.xlsx *.xlsm);;All Files (*)")
        if path:
            self.input_file_input.setText(path)

    def _browse_output_file(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Select output Excel", "", "Excel Files (*.xlsx);;All Files (*)")
        if path:
            self.output_file_input.setText(path)

    def _browse_report_file(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Select report JSON", "", "JSON Files (*.json);;All Files (*)")
        if path:
            self.report_file_input.setText(path)

    def _run_workflow(self) -> None:
        input_file = self.input_file_input.text().strip()
        if not input_file:
            QMessageBox.warning(self, "Missing Input", "Please select input Excel file.")
            return

        workflow_file = self.workflow_file_input.text().strip()
        workflow_name = None if workflow_file else self.workflow_combo.currentText()
        output_file = self.output_file_input.text().strip() or None
        report_file = self.report_file_input.text().strip() or None
        dry_run = self.dry_run_checkbox.isChecked()
        safe_stop = float(self.safe_stop_input.value())

        email_config = EmailRuntimeConfig(
            enabled=bool(
                self.email_host_input.text().strip()
                and self.email_username_input.text().strip()
                and self.email_password_input.text().strip()
            ),
            host=self.email_host_input.text().strip(),
            username=self.email_username_input.text().strip(),
            password=self.email_password_input.text().strip(),
            folder=self.email_folder_input.text().strip() or "INBOX",
        )

        try:
            workflow = load_workflow_from_source(workflow_name=workflow_name, workflow_file=workflow_file or None)
            runner = AutomationRunner(settings=self._settings)
            summary = runner.run_excel_workflow(
                workflow=workflow,
                input_file=Path(input_file),
                output_file=Path(output_file) if output_file else None,
                report_file=Path(report_file) if report_file else None,
                dry_run=dry_run,
                safe_stop_error_rate=safe_stop,
                email_config=email_config,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Run Failed", str(exc))
            return

        self.result_output.setPlainText(json.dumps(summary.to_dict(), indent=2))
        QMessageBox.information(self, "Run Completed", "Workflow run completed successfully.")


class TeachSessionTab(QWidget):
    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = TeachSessionService(settings=settings)
        self._compiler = TeachSessionCompiler(session_service=self._service)
        self._replayer = TeachSessionReplayer(session_service=self._service)
        self._auto_recorder = AutoTeachRecorder(session_service=self._service)
        self._active_record_session_id: str | None = None
        self._record_status = "idle"
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(500)
        self._poll_timer.timeout.connect(self._poll_recorder_state)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        auto_group = QGroupBox("Auto Recorder")
        auto_form = QFormLayout(auto_group)
        self.auto_name_input = QLineEdit()
        self.auto_name_input.setPlaceholderText("Session name for auto recording")
        auto_form.addRow("Session name", self.auto_name_input)
        self.auto_status_label = QLabel("Status: idle")
        auto_form.addRow("Recorder status", self.auto_status_label)
        self.start_auto_button = QPushButton("Start Auto Record")
        self.start_auto_button.clicked.connect(self._start_auto_record)
        self.stop_auto_button = QPushButton("Stop Auto Record")
        self.stop_auto_button.clicked.connect(self._stop_auto_record)
        auto_btn_row = QWidget()
        auto_btn_layout = QHBoxLayout(auto_btn_row)
        auto_btn_layout.setContentsMargins(0, 0, 0, 0)
        auto_btn_layout.addWidget(self.start_auto_button)
        auto_btn_layout.addWidget(self.stop_auto_button)
        auto_form.addRow("", auto_btn_row)
        layout.addWidget(auto_group)

        start_group = QGroupBox("Start Session")
        start_form = QFormLayout(start_group)
        self.session_name_input = QLineEdit()
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self._start_session)
        start_row = QWidget()
        start_layout = QHBoxLayout(start_row)
        start_layout.setContentsMargins(0, 0, 0, 0)
        start_layout.addWidget(self.session_name_input)
        start_layout.addWidget(self.start_button)
        start_form.addRow("Session name", start_row)
        layout.addWidget(start_group)

        event_group = QGroupBox("Record Event")
        event_form = QFormLayout(event_group)
        self.session_id_input = QLineEdit()
        event_form.addRow("Session id", self.session_id_input)

        self.event_type_combo = QComboBox()
        self.event_type_combo.addItems([item.value for item in TeachEventType])
        event_form.addRow("Event type", self.event_type_combo)

        self.payload_key_input = QLineEdit()
        self.payload_key_input.setPlaceholderText("selector")
        self.payload_value_input = QLineEdit()
        self.payload_value_input.setPlaceholderText("input[name='email']")
        payload_row = QWidget()
        payload_layout = QHBoxLayout(payload_row)
        payload_layout.setContentsMargins(0, 0, 0, 0)
        payload_layout.addWidget(self.payload_key_input)
        payload_layout.addWidget(self.payload_value_input)
        event_form.addRow("Payload key/value", payload_row)

        self.sensitive_checkbox = QCheckBox("Sensitive event")
        event_form.addRow("Flags", self.sensitive_checkbox)

        self.add_event_button = QPushButton("Add Event")
        self.add_event_button.clicked.connect(self._add_event)
        event_form.addRow("", self.add_event_button)
        layout.addWidget(event_group)

        checkpoint_group = QGroupBox("Checkpoint")
        checkpoint_form = QFormLayout(checkpoint_group)
        self.checkpoint_name_input = QLineEdit()
        self.checkpoint_button = QPushButton("Add Checkpoint")
        self.checkpoint_button.clicked.connect(self._add_checkpoint)
        checkpoint_row = QWidget()
        checkpoint_layout = QHBoxLayout(checkpoint_row)
        checkpoint_layout.setContentsMargins(0, 0, 0, 0)
        checkpoint_layout.addWidget(self.checkpoint_name_input)
        checkpoint_layout.addWidget(self.checkpoint_button)
        checkpoint_form.addRow("Checkpoint name", checkpoint_row)
        layout.addWidget(checkpoint_group)

        actions_group = QGroupBox("Session Actions")
        actions_form = QFormLayout(actions_group)
        self.finish_button = QPushButton("Finish Session")
        self.finish_button.clicked.connect(self._finish_session)
        actions_form.addRow("", self.finish_button)

        self.export_file_input = QLineEdit()
        self.export_file_input.setPlaceholderText("artifacts/session.json")
        self.export_file_button = QPushButton("Browse...")
        self.export_file_button.clicked.connect(self._browse_export_file)
        export_row = QWidget()
        export_layout = QHBoxLayout(export_row)
        export_layout.setContentsMargins(0, 0, 0, 0)
        export_layout.addWidget(self.export_file_input)
        export_layout.addWidget(self.export_file_button)
        self.export_button = QPushButton("Export Session")
        self.export_button.clicked.connect(self._export_session)
        export_action_row = QWidget()
        export_action_layout = QHBoxLayout(export_action_row)
        export_action_layout.setContentsMargins(0, 0, 0, 0)
        export_action_layout.addWidget(export_row)
        export_action_layout.addWidget(self.export_button)
        actions_form.addRow("Export file", export_action_row)

        self.compile_workflow_id_input = QLineEdit()
        self.compile_workflow_id_input.setPlaceholderText("employee_signup_v1")
        actions_form.addRow("Workflow id", self.compile_workflow_id_input)

        self.compile_file_input = QLineEdit()
        self.compile_file_input.setPlaceholderText("artifacts/employee_signup_v1.workflow.json")
        self.compile_file_button = QPushButton("Browse...")
        self.compile_file_button.clicked.connect(self._browse_compile_file)
        compile_row = QWidget()
        compile_layout = QHBoxLayout(compile_row)
        compile_layout.setContentsMargins(0, 0, 0, 0)
        compile_layout.addWidget(self.compile_file_input)
        compile_layout.addWidget(self.compile_file_button)
        self.compile_button = QPushButton("Compile Session")
        self.compile_button.clicked.connect(self._compile_session)
        compile_action_row = QWidget()
        compile_action_layout = QHBoxLayout(compile_action_row)
        compile_action_layout.setContentsMargins(0, 0, 0, 0)
        compile_action_layout.addWidget(compile_row)
        compile_action_layout.addWidget(self.compile_button)
        actions_form.addRow("Compile file", compile_action_row)

        self.list_button = QPushButton("List Sessions")
        self.list_button.clicked.connect(self._list_sessions)
        actions_form.addRow("", self.list_button)

        self.replay_speed_input = QDoubleSpinBox()
        self.replay_speed_input.setRange(0.1, 10.0)
        self.replay_speed_input.setSingleStep(0.1)
        self.replay_speed_input.setValue(1.0)
        actions_form.addRow("Replay speed", self.replay_speed_input)
        self.replay_repeat_input = QSpinBox()
        self.replay_repeat_input.setRange(1, 1000)
        self.replay_repeat_input.setValue(1)
        actions_form.addRow("Replay repeats", self.replay_repeat_input)
        self.replay_button = QPushButton("Replay Session")
        self.replay_button.clicked.connect(self._replay_session)
        actions_form.addRow("", self.replay_button)
        layout.addWidget(actions_group)

        self.result_output = QTextEdit()
        self.result_output.setReadOnly(True)
        self.result_output.setPlaceholderText("Teach session output will appear here.")
        layout.addWidget(self.result_output)

    def _start_session(self) -> None:
        name = self.session_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Please provide session name.")
            return
        try:
            session = self._service.start_session(name=name)
        except Exception as exc:
            QMessageBox.critical(self, "Start Failed", str(exc))
            return
        self.session_id_input.setText(session.session_id)
        self.result_output.setPlainText(json.dumps(session.model_dump(mode="json"), indent=2))

    def _start_auto_record(self) -> None:
        if self._auto_recorder.is_recording:
            QMessageBox.warning(self, "Recorder Busy", "Auto recorder is already running.")
            return
        name = self.auto_name_input.text().strip() or self.session_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Please provide session name for auto recorder.")
            return
        try:
            session = self._service.start_session(name=name)
            self._active_record_session_id = session.session_id
            self.session_id_input.setText(session.session_id)
            self._auto_recorder.start(session_id=session.session_id)
            self._record_status = "recording"
            self.auto_status_label.setText("Status: recording (press ESC to stop)")
            self._poll_timer.start()
            self.result_output.setPlainText(json.dumps(session.model_dump(mode="json"), indent=2))
            self._minimize_host_window()
        except Exception as exc:
            QMessageBox.critical(self, "Auto Record Failed", str(exc))

    def _stop_auto_record(self) -> None:
        if not self._auto_recorder.is_recording:
            QMessageBox.information(self, "Auto Recorder", "Recorder is not running.")
            return
        try:
            self._auto_recorder.stop(finish_session=True)
            self._record_status = "stopped"
            self.auto_status_label.setText("Status: stopped")
            self._poll_timer.stop()
            self._restore_host_window()
            if self._active_record_session_id:
                session = self._service.get_session(session_id=self._active_record_session_id)
                self.result_output.setPlainText(json.dumps(session.model_dump(mode="json"), indent=2))
        except Exception as exc:
            QMessageBox.critical(self, "Stop Failed", str(exc))

    def _poll_recorder_state(self) -> None:
        if self._record_status != "recording":
            return
        if self._auto_recorder.is_recording:
            return
        self._record_status = "stopped"
        self.auto_status_label.setText("Status: stopped")
        self._poll_timer.stop()
        self._restore_host_window()
        if self._active_record_session_id:
            try:
                session = self._service.get_session(session_id=self._active_record_session_id)
            except Exception:
                return
            self.result_output.setPlainText(json.dumps(session.model_dump(mode="json"), indent=2))

    def _add_event(self) -> None:
        session_id = self.session_id_input.text().strip()
        if not session_id:
            QMessageBox.warning(self, "Missing Session ID", "Please provide session id.")
            return

        payload: dict[str, object] = {}
        key = self.payload_key_input.text().strip()
        value = self.payload_value_input.text().strip()
        if key:
            payload[key] = value

        try:
            session = self._service.add_event(
                session_id=session_id,
                event_type=TeachEventType(self.event_type_combo.currentText()),
                payload=payload,
                sensitive=self.sensitive_checkbox.isChecked(),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Add Event Failed", str(exc))
            return
        self.result_output.setPlainText(json.dumps(session.model_dump(mode="json"), indent=2))

    def _add_checkpoint(self) -> None:
        session_id = self.session_id_input.text().strip()
        name = self.checkpoint_name_input.text().strip()
        if not session_id or not name:
            QMessageBox.warning(self, "Missing Data", "Provide session id and checkpoint name.")
            return
        try:
            session = self._service.add_event(
                session_id=session_id,
                event_type=TeachEventType.CHECKPOINT,
                payload={"name": name},
                sensitive=False,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Checkpoint Failed", str(exc))
            return
        self.result_output.setPlainText(json.dumps(session.model_dump(mode="json"), indent=2))

    def _finish_session(self) -> None:
        session_id = self.session_id_input.text().strip()
        if not session_id:
            QMessageBox.warning(self, "Missing Session ID", "Please provide session id.")
            return
        try:
            session = self._service.finish_session(session_id=session_id)
        except Exception as exc:
            QMessageBox.critical(self, "Finish Failed", str(exc))
            return
        self.result_output.setPlainText(json.dumps(session.model_dump(mode="json"), indent=2))

    def _browse_export_file(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Select session export file", "", "JSON Files (*.json);;All Files (*)")
        if path:
            self.export_file_input.setText(path)

    def _export_session(self) -> None:
        session_id = self.session_id_input.text().strip()
        output_file = self.export_file_input.text().strip()
        if not session_id or not output_file:
            QMessageBox.warning(self, "Missing Data", "Provide session id and export file.")
            return
        try:
            output = self._service.export_session(session_id=session_id, output_file=output_file)
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))
            return
        self.result_output.setPlainText(json.dumps({"session_id": session_id, "output_file": str(output)}, indent=2))

    def _browse_compile_file(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Select compiled workflow file",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if path:
            self.compile_file_input.setText(path)

    def _compile_session(self) -> None:
        session_id = self.session_id_input.text().strip()
        workflow_id = self.compile_workflow_id_input.text().strip()
        output_file = self.compile_file_input.text().strip()
        if not session_id or not workflow_id or not output_file:
            QMessageBox.warning(self, "Missing Data", "Provide session id, workflow id, and output file.")
            return
        try:
            output = self._compiler.compile_to_workflow(
                session_id=session_id,
                workflow_id=workflow_id,
                output_file=output_file,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Compile Failed", str(exc))
            return
        self.result_output.setPlainText(
            json.dumps({"session_id": session_id, "workflow_id": workflow_id, "output_file": str(output)}, indent=2)
        )

    def _list_sessions(self) -> None:
        try:
            sessions = self._service.list_sessions()
        except Exception as exc:
            QMessageBox.critical(self, "List Failed", str(exc))
            return
        payload = [item.model_dump(mode="json") for item in sessions]
        self.result_output.setPlainText(json.dumps(payload, indent=2))

    def _replay_session(self) -> None:
        session_id = self.session_id_input.text().strip()
        if not session_id:
            QMessageBox.warning(self, "Missing Session ID", "Please provide session id.")
            return
        confirm = QMessageBox.question(
            self,
            "Confirm Replay",
            "Replay will control mouse and keyboard on your computer. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._minimize_host_window()
        try:
            summary = self._replayer.replay(
                session_id=session_id,
                speed_factor=float(self.replay_speed_input.value()),
                repeat_count=int(self.replay_repeat_input.value()),
                save_diagnostics=True,
            )
        except Exception as exc:
            self._restore_host_window()
            QMessageBox.critical(self, "Replay Failed", str(exc))
            return
        self._restore_host_window()
        self.result_output.setPlainText(self._format_replay_summary(summary.to_dict()))

    def _format_replay_summary(self, payload: dict[str, object]) -> str:
        diagnostics_raw = payload.get("diagnostics", [])
        diagnostics: list[dict[str, object]] = []
        if isinstance(diagnostics_raw, list):
            diagnostics = [item for item in diagnostics_raw if isinstance(item, dict)]

        failed = [item for item in diagnostics if not bool(item.get("applied", False))]
        summary_block: dict[str, object] = {
            "session_id": payload.get("session_id"),
            "replayed_events": payload.get("replayed_events"),
            "skipped_events": payload.get("skipped_events"),
            "speed_factor": payload.get("speed_factor"),
            "repeat_count": payload.get("repeat_count"),
            "completed_loops": payload.get("completed_loops"),
            "stopped_by_user": payload.get("stopped_by_user"),
            "diagnostics_file": payload.get("diagnostics_file"),
            "failed_event_count": len(failed),
        }

        preview_limit = 20
        failed_preview = failed[:preview_limit]
        output: dict[str, object] = {
            "summary": summary_block,
            "failed_events_preview": failed_preview,
        }
        remaining = len(failed) - len(failed_preview)
        if remaining > 0:
            output["failed_events_remaining"] = remaining
        return json.dumps(output, indent=2)

    def _minimize_host_window(self) -> None:
        host = self.window()
        if isinstance(host, QMainWindow):
            host.showMinimized()

    def _restore_host_window(self) -> None:
        host = self.window()
        if isinstance(host, QMainWindow):
            host.showNormal()
            host.raise_()
            host.activateWindow()


class WorkflowToolsTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        validate_group = QGroupBox("Validate Workflow File")
        validate_form = QFormLayout(validate_group)

        self.workflow_file_input = QLineEdit()
        self.workflow_file_button = QPushButton("Browse...")
        self.workflow_file_button.clicked.connect(self._browse_workflow_file)
        workflow_row = QWidget()
        workflow_layout = QHBoxLayout(workflow_row)
        workflow_layout.setContentsMargins(0, 0, 0, 0)
        workflow_layout.addWidget(self.workflow_file_input)
        workflow_layout.addWidget(self.workflow_file_button)
        validate_form.addRow("Workflow JSON", workflow_row)

        self.validate_button = QPushButton("Validate")
        self.validate_button.clicked.connect(self._validate_workflow)
        validate_form.addRow("", self.validate_button)
        layout.addWidget(validate_group)

        info_group = QGroupBox("Built-in Workflows")
        info_layout = QVBoxLayout(info_group)
        self.builtin_output = QTextEdit()
        self.builtin_output.setReadOnly(True)
        self.builtin_output.setPlainText(json.dumps({"available_workflows": list_available_workflows()}, indent=2))
        info_layout.addWidget(self.builtin_output)
        layout.addWidget(info_group)

        self.result_output = QTextEdit()
        self.result_output.setReadOnly(True)
        self.result_output.setPlaceholderText("Workflow validation summary will appear here.")
        layout.addWidget(self.result_output)

    def _browse_workflow_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select workflow JSON", "", "JSON Files (*.json);;All Files (*)")
        if path:
            self.workflow_file_input.setText(path)

    def _validate_workflow(self) -> None:
        workflow_file = self.workflow_file_input.text().strip()
        if not workflow_file:
            QMessageBox.warning(self, "Missing File", "Please select workflow JSON file.")
            return
        try:
            summary = summarize_workflow(workflow_file)
        except Exception as exc:
            QMessageBox.critical(self, "Validation Failed", str(exc))
            return
        self.result_output.setPlainText(json.dumps(summary, indent=2))
        QMessageBox.information(self, "Validation Completed", "Workflow file is valid.")


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.setWindowTitle(settings.app_name)
        self.resize(980, 760)

        tabs = QTabWidget()
        tabs.addTab(RunWorkflowTab(settings=settings), "Run")
        tabs.addTab(TeachSessionTab(settings=settings), "Teach")
        tabs.addTab(WorkflowToolsTab(), "Workflow")
        self.setCentralWidget(tabs)


def launch_ui(settings: Settings | None = None) -> int:
    app = QApplication(sys.argv)
    resolved_settings = settings or Settings.from_env()
    window = MainWindow(settings=resolved_settings)
    window.show()
    return app.exec()
