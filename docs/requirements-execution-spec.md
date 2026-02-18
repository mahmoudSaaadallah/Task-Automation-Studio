# Task Automation Studio - Execution Requirements (v1)

## 1. Document Goal
Define a precise, implementation-ready baseline for a desktop automation platform that handles repetitive business workflows with high accuracy and full auditability.

## 2. Product Vision
Build a general-purpose desktop automation system (Python, free/open stack) that can automate repeated workflows across web apps, files, and email, with strict validation and controlled failure handling.

## 3. Scope

### 3.1 In Scope (v1 / MVP)
- Desktop app to run automation jobs.
- Workflow engine with ordered steps.
- Connectors for Excel input/output, browser actions, and email OTP retrieval.
- Validation layer before and after each action.
- Retry and fail-safe logic.
- Persistent job state and resumable execution.
- Full run logs and per-record audit trail.
- Manual review queue for uncertain/failed records.

### 3.2 Out of Scope (v1)
- Cloud/SaaS deployment.
- Mobile client.
- AI-driven autonomous decision making.
- Multi-tenant architecture.

## 4. Core Principles
- Accuracy first: no action without pre-check and post-check.
- Idempotency: prevent duplicate processing of the same business record.
- Deterministic behavior: same input + same state -> same output.
- Observable execution: every important action is logged with evidence.
- Safe failure: stop or isolate on repeated errors, never continue blindly.

## 5. Functional Requirements

### FR-1 Workflow Definition
- System shall support workflow templates composed of ordered steps.
- Each step must define:
  - Required inputs
  - Validation rules
  - Timeout
  - Retry policy
  - Success criteria
  - Error code mapping

### FR-2 Data Intake (Excel)
- System shall read employee records from `.xlsx`.
- Required fields for each record:
  - `first_name`
  - `last_name`
  - `email`
- Invalid records must be rejected before execution and marked with explicit reason.

### FR-3 Browser Automation Connector
- System shall execute scripted web actions (open page, fill fields, click, wait, verify).
- Step completion requires explicit UI verification signals (element state/text/URL change).

### FR-4 Email OTP Connector
- System shall fetch verification codes from approved mailbox access.
- OTP extraction must include:
  - Sender/domain check
  - Time window check
  - Pattern validation

### FR-5 Validation and Controls
- System shall enforce pre-check and post-check on each step.
- On check failure, system shall not continue to next step for that record.

### FR-6 Retry and Fail-safe
- System shall support bounded retries with exponential backoff.
- Permanent failure routes record to `Needs Review`.
- If error rate exceeds configurable threshold, job enters `Safe Stop`.

### FR-7 Persistence and Resume
- System shall store job state in SQLite.
- Interrupted jobs shall resume from last committed checkpoint.

### FR-8 Logging and Audit
- System shall store:
  - Job-level logs
  - Record-level status transitions
  - Step-level evidence references
  - Timestamps and execution duration
- Every record must end with one terminal status:
  - `Success`
  - `Failed`
  - `Needs Review`
  - `Skipped`

### FR-9 Manual Review Queue
- System shall provide list of records requiring operator decision.
- Operator may retry, skip, or mark as resolved with note.

### FR-10 Output and Reporting
- System shall produce run summary:
  - Total records
  - Success count
  - Failure count
  - Review queue count
  - Average processing time
  - Error categories

## 6. Non-Functional Requirements

### NFR-1 Accuracy
- Target successful step validation rate: >= 99.5% in controlled test runs.
- Zero silent failures: every failed action must emit explicit error code.

### NFR-2 Reliability
- No data loss for committed statuses during crash/restart.
- Resume must preserve already completed records without duplication.

### NFR-3 Security
- Credentials/secrets must be encrypted at rest on local machine.
- Principle of least privilege for email and system access.
- Sensitive values must be masked in logs.

### NFR-4 Performance
- Must process large batches (10k+ records) in queue-based execution mode.
- UI remains responsive during long-running jobs.

### NFR-5 Usability
- Operator can configure and launch a workflow without code edits.
- Error messages must be actionable and human-readable.

## 7. Proposed Technical Stack (Free)
- Python 3.12+
- UI: PySide6
- Browser automation: Playwright
- Data handling: pandas + openpyxl
- Validation: pydantic
- Retry: tenacity
- Storage: SQLite + SQLAlchemy
- Packaging: PyInstaller

## 8. Data Model (Initial)

### 8.1 Entities
- `workflow`
- `job_run`
- `record`
- `step_execution`
- `audit_event`
- `credential_ref`

### 8.2 Required Keys
- Business unique key for records: `email`
- Technical key: UUID for every job and step execution

## 9. Zoom Example as Template (Reference Workflow)
1. Load records from Excel.
2. Validate mandatory fields and email format.
3. Open signup page.
4. Fill first name, last name, email.
5. Submit signup form.
6. Wait for OTP email and parse code.
7. Enter OTP and confirm.
8. Verify account creation success signal.
9. Persist final status and evidence.

Note: this is one workflow template; engine must stay generic for other repetitive tasks.

## 10. MVP Acceptance Criteria
- Can run one full workflow template from UI.
- Can process at least 500 records in one run with resumable checkpointing.
- Produces complete run report and per-record terminal status.
- Demonstrates idempotency (same record not processed twice by mistake).
- Demonstrates manual review loop for unresolved failures.

## 11. Delivery Plan (High Level)
1. Core engine + data model + logging.
2. Excel connector + record validation.
3. Browser connector + step verification framework.
4. Email OTP connector + parsing safeguards.
5. Desktop UI for job orchestration and review queue.
6. Hardening: retries, safe stop, resume tests, packaging.

## 12. Risks and Mitigations
- UI changes in target websites:
  - Mitigation: robust selectors + fallback strategies + fast failure alerts.
- OTP delays or mailbox noise:
  - Mitigation: sender/time filters + bounded wait + review routing.
- Operator misconfiguration:
  - Mitigation: config schema validation + pre-run dry check.
- Data quality issues in source file:
  - Mitigation: strict input validator and reject list before execution.

