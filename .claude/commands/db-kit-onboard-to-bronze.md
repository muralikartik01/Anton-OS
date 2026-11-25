---
description: Start a DB-Kit source_onboarding_to_bronze workflow run for a given scope
argument-hint: <table1,table2,... | source-system/schema filter>
---

Start a new `source_onboarding_to_bronze` workflow run (`workflows/templates/source-onboarding-to-bronze.yaml`) for scope: $ARGUMENTS

1. Generate a `run_id` (e.g. `sob-<project-id>-<timestamp>`) and create `observability/run-records/<run_id>.yaml` per `observability/run-records/_schema.md`, with `workflow_id: source_onboarding_to_bronze`, `state: created`, and `input_parameters.scope` set from the argument above. If no argument was given, ask for one before proceeding — do not guess a scope.
2. Follow `workflows/templates/source-onboarding-to-bronze.yaml` step by step: `source_onboarding` → `quality_check` → `bronze_mapping` → `bronze_generation` → `report`, using the agent and skills named for each step.
3. After every step, update the run record's `steps` entry (status, output_refs, timestamps) and `current_step` before moving to the next one.
4. The `quality_check` step is advisory, not a gate — proceed to `bronze_mapping` regardless of its findings, but carry any fail/blocked rule into the final report rather than letting it quietly disappear.
5. If any step cannot complete, set `state: blocked`, record why in the step's `notes`, and stop — report the blocker rather than continuing past it. The run can be continued later with `/db-kit-resume <run_id>`.
6. On completion, set `state: completed`, write `completion_summary`, and report the path to `artifacts/reports/<project-id>/<run_id>/onboarding-report.md` plus a short summary covering: what was onboarded, what the quality checks found, and what Bronze artifacts were generated.

This workflow has no approval checkpoint (see the template's `approval_gates`) — it stops at Bronze, applies no business logic, and writes no code to a real connection. `hooks/pre-execution/` still apply as a uniform backstop.
