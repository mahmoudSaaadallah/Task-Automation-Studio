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
This is a production-oriented scaffold (phase 1). Business-specific steps and integrations will be implemented incrementally.
