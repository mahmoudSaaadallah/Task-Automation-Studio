# 03. Teach Session and Replay Flow

## Objective
Define how a non-technical user can teach the system a process once, then replay it safely on many records.

## Teach session lifecycle
1. `Start Session`
- User chooses session name and target app category (browser-first in v1).
- Recorder starts with explicit permission prompt.

2. `Capture Actions`
- Recorder stores normalized events:
  - open page
  - click target
  - fill text
  - wait condition
  - copy/paste usage
  - app/window switch
- Sensitive inputs are masked by default.

3. `Checkpoint Tagging`
- User can mark important checkpoints:
  - "Email submitted"
  - "OTP received"
  - "Account created"
- Checkpoints later become post-check assertions.

4. `Compile Session`
- Compiler converts captured events to typed workflow steps.
- Ambiguous selectors are flagged for user review.

5. `Bind Data`
- User maps fields to input columns (e.g., `email -> Excel.email`).
- Binding validation blocks save if required fields are missing.

6. `Dry Run Validation`
- Run on sample records.
- Must pass required checks before live execution unlocks.

7. `Live Replay`
- Executes on batch with safety controls and full audit.

## Replay safety gates
- Gate 1: workflow schema validation.
- Gate 2: binding completeness validation.
- Gate 3: connector permission validation.
- Gate 4: dry-run pass threshold.
- Gate 5: operator confirmation for live-run.

## Failure model
- Step failure types:
  - `selector_not_found`
  - `timeout`
  - `otp_not_found`
  - `validation_failed`
  - `permission_denied`
- Route policy:
  - recoverable -> retry
  - unresolved -> `Needs Review`
  - high-rate failures -> `Safe Stop`

## Accuracy controls
- Pre-check and post-check mandatory for mutating steps.
- No implicit success allowed.
- Evidence required (signal, text match, or state transition).

## Human-in-the-loop behavior
- Review queue shows:
  - record id/email
  - failed step
  - failure code
  - evidence snapshot reference
- Operator actions:
  - retry record
  - skip record
  - edit mapping then retry
