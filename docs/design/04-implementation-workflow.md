# 04. Implementation Workflow

## Goal
Translate design into a controlled build plan with small reversible increments.

## Engineering policy
- Atomic commits only.
- One feature slice per commit.
- Each slice must include:
  - implementation
  - validation (tests or runnable check)
  - docs update if behavior changes

## Phase plan

### Phase A: Recorder foundation
Deliverables:
- Teach session domain model.
- Event capture service interface.
- Session persistence table and files.
- Session export/import format.

Exit criteria:
- Can record and save a session file.
- Session validates against `teach-session.schema.json`.

### Phase B: Workflow compiler
Deliverables:
- Event-to-step conversion rules.
- Selector normalization logic.
- Ambiguity detector and review flags.
- Workflow JSON generation.

Exit criteria:
- Generated workflow validates against `workflow.schema.json`.
- At least one sample teach session compiles to runnable workflow.

### Phase C: Replay runtime v2
Deliverables:
- Workflow loader from JSON.
- Typed action executors.
- Data binding resolver.
- Enhanced retry and post-check evidence policy.

Exit criteria:
- Dry-run on 100+ records with deterministic output.
- Duplicate handling and safe-stop verified by tests.

### Phase D: UI orchestration
Deliverables:
- Teach session controls (start/stop/save).
- Workflow review screen.
- Run monitor with review queue.

Exit criteria:
- Non-technical operator can complete end-to-end flow without code.

### Phase E: Hardening
Deliverables:
- Secret handling integration in UI flows.
- Structured error catalog.
- Better evidence capture and searchable audit logs.
- Packaging and installer script.

Exit criteria:
- Stable run on pilot batch.
- Recovery and resume behavior validated.

## Test strategy by phase
- Unit tests for schemas, compiler rules, and step executors.
- Integration tests for Excel -> runner -> SQLite -> reports.
- Smoke tests for CLI and basic UI startup.

## Release checkpoints
- `v0.2`: Teach session recording (technical preview).
- `v0.3`: Workflow compilation + dry-run replay.
- `v0.4`: Operator-first UI flow.
- `v1.0`: Production-ready browser-first automation.
