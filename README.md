# Task Automation Studio

Desktop-first Python platform for high-accuracy repetitive task automation.

## Why this project
- Reduce manual repetitive work.
- Keep strict control on data quality and execution safety.
- Provide full audit trail for each processed record.

## MVP focus
- Workflow engine with deterministic step execution.
- Excel input/output connector.
- Browser automation connector.
- Email OTP retrieval connector.
- SQLite persistence with resumable jobs.
- Manual review queue for failed/uncertain records.

## Quick start
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
python -m task_automation_studio.app --ui
```

## CLI usage
Dry run (recommended first):
```bash
tas run --workflow zoom_signup --input-file data/employees.xlsx --dry-run
```

Live run (connectors must be configured):
```bash
tas run --workflow zoom_signup --input-file data/employees.xlsx --live-run \
  --email-host imap.example.com --email-username user@example.com --email-password SECRET
```

Outputs:
- Excel results file is generated under `artifacts/` (or custom `--output-file`).
- JSON run report is generated under `artifacts/` (or custom `--report-file`).
- SQLite state is stored at `data/app.db` by default.

## Project layout
```text
src/task_automation_studio/
  app.py
  config/
  core/
  connectors/
  persistence/
  services/
  ui/
  utils/
  workflows/
tests/
docs/
```

## Current status
Runtime phase 1 is implemented:
- End-to-end run pipeline (Excel -> workflow engine -> SQLite -> report).
- Retry + safe-stop + duplicate-email protection per run.
- Strict fail behavior for unimplemented live browser handlers.

Next phase: implement real Playwright handlers for each browser action in target workflows.
