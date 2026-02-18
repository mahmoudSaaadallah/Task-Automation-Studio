# Design Docs

This folder defines the target design for evolving Task Automation Studio from workflow-coded automation into a broader no-code RPA desktop platform.

## Document map
- `01-architecture-overview.md`: system architecture, runtime layers, and execution contracts.
- `02-workflow-dsl.md`: no-code workflow runtime format and validation contract.
- `schemas/workflow.schema.json`: JSON schema for workflow files.
- `examples/zoom_signup.workflow.json`: reference workflow example.

## Design rules
- Accuracy before speed.
- No silent success.
- Every step must be verifiable.
- Every run must be auditable.
