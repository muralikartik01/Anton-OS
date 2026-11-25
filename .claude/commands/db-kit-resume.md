---
description: Resume a DB-Kit workflow run from its run record, in this or a new session
argument-hint: <run-id>
---

Resume workflow run: $ARGUMENTS

1. Read `observability/run-records/$ARGUMENTS.yaml`. If it doesn't exist, stop and say so — do not guess at a run's state.
2. Load the workflow template named in the run record's `workflow_id` (via `workflows/registry.yaml`) to know the full step sequence.
3. Load **only** the files listed under completed steps' `output_refs` and `context_references` — do not re-run completed steps or re-derive their output from scratch.
4. Print a resume summary: workflow id, current state, which steps are completed vs. pending, and any blocker recorded in `notes`.
5. If `state: awaiting_approval`, re-present the artifact awaiting approval (e.g. the migration blueprint) and ask for approval before continuing — do not assume prior approval carried over.
6. If `state: blocked`, state the blocker from the run record and ask how to proceed rather than retrying blindly.
7. Otherwise, continue execution from `current_step` through the remaining steps in the workflow template, updating the run record after each one exactly as a fresh run would.
