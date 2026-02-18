from __future__ import annotations

import json
import sys
from pathlib import Path

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
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from task_automation_studio.config.settings import Settings
from task_automation_studio.services.executors import EmailRuntimeConfig
from task_automation_studio.services.runner import AutomationRunner
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


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.setWindowTitle(settings.app_name)
        self.resize(980, 760)

        tabs = QTabWidget()
        tabs.addTab(RunWorkflowTab(settings=settings), "Run")
        tabs.addTab(self._build_placeholder_tab("Teach tools are available in CLI and will be added here next."), "Teach")
        tabs.addTab(self._build_placeholder_tab("Workflow tools are available in CLI and will be added here next."), "Workflow")
        self.setCentralWidget(tabs)

    def _build_placeholder_tab(self, text: str) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        label = QLabel(text)
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch()
        return tab


def launch_ui(settings: Settings | None = None) -> int:
    app = QApplication(sys.argv)
    resolved_settings = settings or Settings.from_env()
    window = MainWindow(settings=resolved_settings)
    window.show()
    return app.exec()
