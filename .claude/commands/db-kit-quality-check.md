---
description: Start a DB-Kit data_quality_check workflow run for a given scope
argument-hint: <table1,table2,... | source-system/schema filter>
---

Start a new `data_quality_check` workflow run (`workflows/templates/data-quality-check.yaml`) for scope: $ARGUMENTS

1. Generate a `run_id` (e.g. `dqc-<project-id>-<timestamp>`) and create `observability/run-records/<run_id>.yaml` per `observability/run-records/_schema.md`, with `workflow_id: data_quality_check`, `state: created`, and `input_parameters.scope` set from the argument above. If no argument was given, ask for one before proceeding — do not guess a scope.
2. Follow `workflows/templates/data-quality-check.yaml` step by step: `scope_resolution` → `profiling` → `rule_generation` → `check_execution` → `report`, using the agent and skill named for each step.
3. After every step, update the run record's `steps` entry (status, output_refs, timestamps) and `current_step` before moving to the next one.
4. If any step cannot complete, set `state: blocked`, record why in the step's `notes`, and stop — report the blocker rather than continuing past it. The run can be continued later with `/db-kit-resume <run_id>`.
5. On completion, set `state: completed`, write `completion_summary`, and report the path to `artifacts/reports/<project-id>/<run_id>/quality-report.md` plus a short summary of what the checks found.

This workflow has no approval checkpoint (gap-resolutions design doc §2/§4 and the workflow template's `approval_gates`) — every step is read-only against a non-production connection. `hooks/pre-execution/` still apply as a uniform backstop.
