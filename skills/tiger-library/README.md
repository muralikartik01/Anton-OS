# Onboarded skills (from Tiger Analytics' Databricks Copilot library)

Copied in full on 2026-11-24 from a tested, production skill library (originally built for VS Code Copilot against a Databricks/PySpark/Unity Catalog stack, PepsiCo DTV-flavored in places) at the user's request, per `docs/reference/tiger-copilot-instructions.md`. **Stored here as reference material, not wired in.** They live under DB-Kit's `skills/` tree but in this subfolder, which Claude Code does not auto-discover, so they never trigger on their own and no workflow uses them. DB-Kit's own skill-docs (`skills/<category>/*.md`) cite them via "Adapted from" lines. To invoke one directly, copy its folder to `.claude/skills/`.

## Platform-scope caveat

DB-Kit's pilot now targets **Databricks (Unity Catalog)** via the `db-kit-databricks` MCP server. This library was copied in wholesale; its generic logic has been adapted into DB-Kit's own `skills/*.md` docs (each carries an "Adapted from" line), and workflow steps cite those docs, not these. Do not wire a DB-Kit agent to one of these skills without first confirming the required MCP server/tooling actually exists in this project's `config/integrations.yaml`.

| Skill | Platform dependency | Status for Phase 1 |
|---|---|---|
| `data-modeling` | None (CSV/spec-driven) | **Usable now** — overlaps `skills/medallion-design`, `skills/source-to-target-mapping` |
| `data-profiling` | Databricks SQL MCP | Needs adapting to a generic SQL connection before use; overlaps `skills/source-analysis/data-profiling.md` |
| `sttm-to-sql` | None (NorthStar project conventions, not Tiger/Databricks) | **Usable now** — overlaps `skills/sql-migration` |
| `sttm-validator` | None | **Usable now** — no DB-Kit equivalent existed; a real gap this fills |
| `drd-dat-gap-assessment` | Databricks MCP; DRD/DAT `.xlsx` artifact types DB-Kit doesn't use | Reference only — introduces artifact types outside the current Project Context Model |
| `lineage-extraction` | A specific Databricks `audit_parameters` schema (explicitly a "worked example, not drop-in") | Out of scope — conceptually overlaps `db-kit-context` MCP's `get_lineage`, implemented against a schema this project doesn't have |
| `gold-catalog` | Unity Catalog | Out of scope — Gold layer isn't in Phase 1 scope at all (`rules/medallion/layer-conventions.md`) |
| `notebook-creation`, `notebook-creation-generic` | Databricks notebooks, STTM CSV, PepsiCo/Tiger framework conventions | Out of scope — this pilot generates SQL/config, not Databricks notebooks |
| `databricks-cluster-sizer`, `cluster-sizing-forecast` | Databricks SQL MCP, Unity Catalog system tables | Out of scope — no Databricks cluster exists in this pilot |
| `databricks-test-runner` | Databricks SQL MCP | Adapted into DB-Kit's `skills/data-quality/quality-check-execution.md` (status model, pass/fail criteria) |
| `sql-to-json` | NorthStar project's own JSON config framework | Out of scope — DB-Kit doesn't use this config format |
| `code-review`, `code-review-tiger`, `code-optimization` | Databricks notebooks (`.py`), Tiger/PepsiCo standards | Not yet wired to a DB-Kit agent — generalizing these to review DB-Kit's own generated SQL (instead of Databricks notebooks) is future work |
| `create-pull-request` | Azure Repos CLI/REST | Not yet wired — DB-Kit doesn't currently have a PR-creation step in any workflow |
| `create-unit-test-cases` | Databricks notebooks | Not yet wired — DB-Kit's validation workflow tests data, not notebook code, today |
| `code-documentation` | Databricks notebook template | Not yet wired — DB-Kit's `migration-review` skill covers the equivalent reporting role |

## Relationship to DB-Kit's own `skills/` directory

`skills/` (repo root) holds DB-Kit's own framework skill-docs, referenced by name from `agents/*.md` contracts and `workflows/templates/*.yaml` steps. `skills/tiger-library/` (this directory) holds directly Claude-Code-invokable skills. Nothing in `workflows/templates/` currently points at anything under `skills/tiger-library/` — that wiring is deliberately left for a follow-up decision once it's clear which remaining skills get adapted.
