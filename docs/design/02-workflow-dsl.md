# 02. Workflow DSL (No-Code Runtime Contract)

## Goal
Define a stable workflow format that:
- can be generated from teach sessions,
- can be edited safely by operators,
- can be executed deterministically by the engine.

## File format
- JSON document with strict schema validation.
- Schema file: `docs/design/schemas/workflow.schema.json`.

## Top-level structure
- `workflow_id`: unique identifier.
- `name`: human-readable workflow name.
- `version`: workflow version string.
- `mode`: `browser_first` for v1.
- `steps`: ordered list of typed steps.
- `bindings`: data mapping rules from input source to step parameters.

## Step model
Each step includes:
- `id`: unique in workflow.
- `type`: action type (`open_url`, `fill_field`, `click`, `wait_for`, `fetch_otp`, ...).
- `params`: step-specific parameters.
- `required_inputs`: fields required from record/bindings.
- `pre_check`: expected state before action.
- `post_check`: expected state after action.
- `retry`: retry policy (`max_attempts`, `backoff_seconds`).
- `on_failure`: `fail_record` or `needs_review`.

## Binding model
`bindings` maps record fields to step parameters using placeholders:
- Example placeholder: `{{record.email}}`.
- The compiler should generate bindings from teach session when possible.

## Validation rules
- Unknown `type` is invalid.
- Missing required parameters is invalid.
- Missing `post_check` for mutating actions is invalid.
- `max_attempts` must be >= 1.

## Example
See: `docs/design/examples/zoom_signup.workflow.json`.
