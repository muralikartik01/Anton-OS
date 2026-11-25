# Run-record schema

One file per workflow run: `observability/run-records/<run-id>.yaml`. This is the single source of truth for workflow state (gap-resolutions design doc §3) — it holds **references** to artifacts, never their content, so resuming a run never means re-loading everything.

```yaml
run_id: string
workflow_id: string          # e.g. data_quality_check, legacy_to_bronze_silver_migration
workflow_version: string
project_id: string
state: created | context_loading | discovery | planning | awaiting_approval |
       executing | validating | reviewing | completed | failed | blocked | cancelled
current_step: string         # matches a step id in the workflow's template yaml
input_parameters: object     # what the user passed when the run was started
steps:
  - id: string
    status: pending | in_progress | completed | blocked | failed
    started_at: datetime
    completed_at: datetime
    output_refs: [string]     # file paths, never inlined content
    notes: string             # e.g. why a step is blocked
context_references: [string]  # MCP query results or files consulted, by path/id
approvals:
  - stage: string
    approved_by: string
    approved_at: datetime
    scope: string
errors: [string]
created_at: datetime
updated_at: datetime
completion_summary: string
```

`/db-kit-resume <run-id>` reads this file, loads only the files listed under `output_refs`/`context_references` for completed steps, and continues at `current_step`.
