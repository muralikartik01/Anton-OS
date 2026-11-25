---
description: Show available DB-Kit commands and workflows (db-kit --help)
argument-hint: (none)
---

Print a concise DB-Kit reference. Do not run any workflow step or touch any file — this is read-only output. Base it on `docs/DEVELOPER-HANDBOOK.md` and `workflows/registry.yaml`, and format it as:

```
DB-Kit — Phase 1 (source -> Databricks landing -> Bronze -> Silver pilot)

Commands:
  /db-kit-quality-check <scope>       Run data_quality_check (profile -> DQ rules -> checks -> report). No approval gate.
  /db-kit-onboard-to-bronze <scope>   Run source_onboarding_to_bronze (onboard -> DQ advisory -> Bronze artifacts -> report). No approval gate.
  /db-kit-migrate [--source databricks:<cat>.<sch> | azuresql:<sch> | postgres:<sch>] [--target databricks] --landing <cat>.<sch> [--bronze ..] [--silver ..] [--scope t1,t2] [--jdbc-secret-scope <name>] [--dry-run]
                                      Run legacy_to_bronze_silver_migration (8 stages, approval gate before generation/execution).
                                      Source/target are inputs: databricks source = data already in landing; azuresql or postgres source adds a landing load.
  /db-kit-resume <run-id>             Resume any workflow run from observability/run-records/<run-id>.yaml.
  /db-kit-help                        Show this help.

  <scope> = comma-separated table names, or a source-system/schema filter.

Workflows registered (workflows/registry.yaml):
  - data_quality_check              active
  - source_onboarding_to_bronze     active
  - legacy_to_bronze_silver_migration   active (/db-kit-migrate)

Where things land:
  Run state     -> observability/run-records/<run-id>.yaml
  Artifacts      -> artifacts/{validation,migration-plans,generated-code,reports}/<project-id>/<run-id>/

Safety:
  6 PreToolUse hooks always on (.claude/settings.json): secrets block, destructive-SQL block,
  production-write block, MCP integration allowlist, validation-before-review gate, blueprint-approval gate (blocks execute_statement).

Docs:
  docs/DEVELOPER-HANDBOOK.md   Full usage guide
  DB-Kit-V1-spec.md            Framework spec
  docs/superpowers/specs/2026-11-23-db-kit-v1-gap-resolutions-design.md   Phase 1 design decisions
```

If `workflows/registry.yaml` has changed (workflows added/removed) since this command was written, reflect the current file's contents rather than the literal list above.
