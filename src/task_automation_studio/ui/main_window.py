from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Task Automation Studio")
        self.resize(700, 420)

        title = QLabel("Task Automation Studio")
        status = QLabel("Scaffold ready. Workflow execution UI will be added in next phase.")
        run_button = QPushButton("Run Workflow (Coming Soon)")
        run_button.setEnabled(False)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(title)
        layout.addWidget(status)
        layout.addWidget(run_button)
        self.setCentralWidget(container)


def launch_ui() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
