# Security and privacy rules

- Never commit or log secrets, credentials, or connection strings in plaintext.
- Never write to a connection tagged `production` in `integrations.yaml`/`project.yaml` unless `production_writes_enabled: true` and the current run has an explicit approval record.
- Never execute a statement matching the destructive-SQL pattern list (`DROP`, `TRUNCATE`, `DELETE` without `WHERE`, `ALTER ... DROP COLUMN`, etc.) against a real connection without a per-statement approval in the run record.
- Never call an MCP tool or integration that is not declared in `integrations.yaml`.
- These boundaries are enforced by hooks under `hooks/pre-execution/` (see `docs/superpowers/specs/2026-11-23-db-kit-v1-gap-resolutions-design.md` §2) — treat a hook block as final, not as something to retry around.
- Avoid duplicating raw sensitive source data into `artifacts/` or `observability/` records.
