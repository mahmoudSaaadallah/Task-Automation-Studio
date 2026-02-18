# 01. Architecture Overview

## Purpose
Define a reliable architecture for a desktop automation platform that can be taught by non-programmers, replayed safely on large batches, and audited end-to-end.

## Product direction
Current model: hardcoded workflow steps.

Target model:
- `Teach Mode`: user demonstrates a process once.
- `Workflow Builder`: system converts observed actions into structured workflow steps.
- `Replay Mode`: engine executes workflow with data mapping and safety controls.

## System layers
1. `Desktop Shell (UI)`
- Start/stop teach sessions.
- Review and edit generated workflows.
- Launch runs, monitor progress, inspect review queue.

2. `Teach Recorder`
- Captures user events from supported channels:
  - Browser actions
  - Clipboard use
  - Keyboard text input (masked where needed)
  - Window/app transitions
- Produces normalized events (not raw device-only events).

3. `Workflow Compiler`
- Converts captured events into typed steps (`open_url`, `fill_field`, `click`, `wait_for`, `read_email_otp`, `write_cell`, ...).
- Suggests parameterized selectors and data bindings.
- Flags ambiguous actions for manual confirmation.

4. `Execution Engine`
- Runs step-by-step with:
  - Pre-check
  - Action
  - Post-check
  - Retry policy
  - Error classification
- Supports `dry-run` and `live-run`.

5. `Validation & Safety Controller`
- Idempotency guards (e.g., no duplicate email processing in a run).
- Safe-stop threshold enforcement.
- Kill switch.
- Human review queue for unresolved records.

6. `Connector Layer`
- Excel connector (read/write).
- Browser connector (Playwright-backed).
- Email connector (OTP retrieval).
- Future connectors (desktop apps, APIs).

7. `Persistence & Audit`
- SQLite for runs, records, statuses, and step events.
- Artifacts store for reports and evidence.
- Immutable audit events per step transition.

## Runtime flow (high level)
1. User starts teach session and demonstrates process.
2. Recorder captures events and compiler builds draft workflow.
3. User reviews workflow and maps step inputs to data columns.
4. Runner executes workflow on batch records.
5. Engine writes record status and evidence continuously.
6. Failed/ambiguous records route to review queue.
7. Summary report generated (JSON + Excel output sheet).

## Accuracy contract (must-haves)
- No step may be marked successful without explicit verification evidence.
- No unsupported action may fallback to implicit success.
- Failed checks must carry machine-readable error codes.
- Resume logic must avoid reprocessing completed records.

## Security model (v1)
- Secrets in OS keyring, never plain text in workflow files.
- Mask sensitive values in logs and reports.
- Restrict live-run permissions to approved connectors.

## Scope boundaries for next implementation phase
In scope:
- Browser-first teach and replay.
- Excel-driven batch execution.
- OTP email fetch integration.
- Step-level verification and evidence.

Out of scope:
- Full desktop OCR automation.
- Autonomous decision making without rules.
- Distributed execution.
