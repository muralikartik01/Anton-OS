# DB-Kit Developer Handbook

DB-Kit is a repository-based Claude Code framework for data-engineering migration work. This is the day-to-day guide for using it. For the full architecture and rationale, see `DB-Kit-V1-spec.md` (the spec) and `docs/superpowers/specs/2026-11-23-db-kit-v1-gap-resolutions-design.md` (the Phase 1 design decisions referenced throughout this handbook).

Quick start: run `/db-kit-help` inside Claude Code at any time for a condensed version of this document.

## 1. What DB-Kit actually is

DB-Kit is **not** a separate program you run. It's a set of files inside this repo — rules, agents, skills, workflow templates, hooks, and slash commands — that shape how Claude Code behaves when you're doing migration work here. You interact with it by:

1. Opening Claude Code in this repo.
2. Typing a `/db-kit-*` slash command to start or resume a workflow.
3. Letting it work through the steps, reviewing/approving where the workflow calls for it.

Everything a run produces — plans, generated SQL, validation results, reports — lands under `artifacts/`, and the run's own state lives in `observability/run-records/<run-id>.yaml`, so a run can be resumed later, even in a new session.

## 2. One-time setup per project

Before running any workflow, fill in:

| File | What to set |
|---|---|
| `config/project.yaml` | Project id/name, source/target platform, migration scope (bronze/silver), policy flags |
| `config/integrations.yaml` | Connection details for source/target, and MCP server status (`mock` vs `real`) |
| `config/framework.yaml` | Hook enforcement levels, resume mechanism (defaults are sane — only change if you know why) |

Phase 1 pilot defaults (already set): a real, non-production Databricks workspace (Unity Catalog), Bronze+Silver scope, Neo4j context graph consumed via MCP (currently the mock server at `integrations/mcp/neo4j-context/mock_server/`, describing a retail dataset: customers, products, orders, order_items).

**Databricks connection:** build the connector venv (`integrations/mcp/databricks-sql/README.md`), export `DB_KIT_DBX_HOST`, `DB_KIT_DBX_HTTP_PATH`, `DB_KIT_DBX_TOKEN` in the shell that launches Claude Code, and approve the project MCP servers from `.mcp.json`. Catalog and schema names are never configured — you pass them per run.

## 3. The three workflows

| Command | Workflow | What it does | Approval gate |
|---|---|---|---|
| `/db-kit-quality-check <scope>` | `data_quality_check` | Profile scope → generate DQ rules → run checks → report | None (read-only) |
| `/db-kit-onboard-to-bronze <scope>` | `source_onboarding_to_bronze` | Onboard source → DQ check (advisory) → map + generate **Bronze-only** artifacts → report | None (raw copy, reversible, no business logic) |
| `/db-kit-resume <run-id>` | (any) | Resume a run from its run record, in this or a new session | Re-asserts any pending approval, doesn't assume it carried over |

`<scope>` is either an explicit comma-separated table list, or a source-system/schema filter.

| `/db-kit-migrate [--source databricks:<cat>.<sch> \| azuresql:<sch> | postgres:<sch>] [--target databricks] --landing <cat>.<sch> [--bronze ..] [--silver ..] [--scope t1,t2] [--jdbc-secret-scope <name>] [--dry-run]` | `legacy_to_bronze_silver_migration` | Discovery → assessment → blueprint → **approval** → generate notebooks/SQL → validate (materializes Bronze/Silver in Databricks, then checks) → review → report | **Yes**, before generation/execution: the blueprint must be approved (recorded in the run record) or `execute_statement` is blocked by hook |

**Source and target are inputs.** With `--source databricks:<cat>.<sch>` (or just `--landing`) the data is already in landing. With `--source postgres:<schema>` (Azure Database for PostgreSQL via `db-kit-postgres`, env vars `DB_KIT_PG_*`) the same flow applies. With `--source azuresql:<schema>` DB-Kit reads the Azure SQL database through the read-only `db-kit-azuresql` connector (`DB_KIT_AZSQL_SERVER/DATABASE/USER/PASSWORD` env vars; see `integrations/mcp/azuresql/README.md`), maps T-SQL types to Spark, and after the approval gate loads it into landing with JDBC SQL (the JDBC user/password live in a Databricks secret scope you create once, passed as `--jdbc-secret-scope`). Targets other than `databricks` stop the run.

Each run also writes `profile.csv`, `quality-rules.csv` (validation folder) and one `docs/<table>_transformation.md` per generated notebook, alongside the markdown reports.

`/db-kit-migrate` flow: Bronze = typed casts + ingestion metadata + quarantine of bad rows; Silver = dedup + business rules + dimensional model (dim/fact). Only the Validation Agent executes SQL, only after approval.

### Typical sessions

**"Is this source clean enough to care about?"**
```
/db-kit-quality-check customers,orders,order_items
```
Produces a test plan + pass/fail/blocked results report. Nothing is written anywhere else.

**"Land this source as Bronze so we can start working with it."**
```
/db-kit-onboard-to-bronze finance.ledger_entries
```
Runs a DQ pass alongside (doesn't block), then generates Bronze ingestion SQL/config under `artifacts/generated-code/<project-id>/<run-id>/bronze/`. DQ findings are carried into the final report, not dropped, so a later Silver effort starts from known issues.

**Picking a run back up**
```
/db-kit-resume sob-example-project-20261124-1
```
Works identically whether it's the same session or a brand-new one — the run record is the only thing it trusts.

## 4. What happens under the hood

Each workflow template (`workflows/templates/*.yaml`) is a step list. Each step names:
- an **agent** (`agents/*.md` — discovery, migration-architect, transformation, validation, review) that acts in that step,
- the **skill(s)** (`skills/*/*.md`) that agent follows for *how* to do the work,
- its outputs, written under `artifacts/`.

Every step updates the run record (`observability/run-records/<run-id>.yaml`) before moving to the next one — status, output file references (never inlined content), timestamps. If a step can't complete, the run goes to `state: blocked` with the reason recorded, instead of guessing or skipping.

**Rules** (`rules/*/*.md`) are always-loaded constraints — safety boundaries, SQL standards, medallion-layer conventions, target-platform specifics. They apply regardless of which workflow or agent is active.

## 5. Safety hooks (always on)

Six `PreToolUse` hooks are wired in `.claude/settings.json` and fire on every matching tool call, not just inside a workflow:

| Hook | Blocks |
|---|---|
| `block_secrets.py` | Writing anything that looks like a credential/secret |
| `block_destructive_sql.py` | `DROP`/`TRUNCATE`/destructive SQL patterns, unless explicitly approved |
| `check_production_target.py` | Any write targeting a connection flagged `production: true` |
| `check_integration_allowlist.py` | MCP calls to operations not in that server's `allowed_operations` |
| `require_validation_complete.py` | Moving to a review/report step before validation results are complete |
| `require_blueprint_approval.py` | `execute_statement` on Databricks unless the run record holds a `migration_blueprint` approval |

These are pattern/config-based, not semantic — e.g. `block_destructive_sql.py` matches literal text, so a commit message that merely *mentions* "DROP TABLE" in prose will also get blocked. That's a known, honest limitation, not a bug to route around; rephrase instead.

## 6. Context: what comes from Neo4j vs. the repo

- **Neo4j (via the `db-kit-context` MCP server)**: discovery-side knowledge only — schema, lineage, entities — read-only plus one write path (`annotate_entity`, for DB-Kit to leave discovery annotations back on the graph). It's maintained by a separate team; DB-Kit never treats it as run state.
- **Everything else** (decisions, validation results, migration plans, run records) lives in repo files under `context/`, `artifacts/`, and `observability/`.

Right now the MCP server is a **mock** (`integrations/mcp/neo4j-context/mock_server/`) — see `integrations/mcp/neo4j-context/CONTRACT.md` for the tool contract the real server needs to satisfy.

## 7. Directory map

```
agents/              Agent contracts (discovery, migration-architect, transformation, validation, review)
rules/               Always-loaded constraints (core, security, data-engineering, medallion, target-platform)
skills/              DB-Kit's own framework skill-docs, referenced by name from agents/workflows
workflows/templates/ Workflow step definitions (yaml)
workflows/registry.yaml   List of registered workflows
.claude/commands/    Slash commands (db-kit-quality-check, db-kit-onboard-to-bronze, db-kit-resume, db-kit-help)
skills/tiger-library/      Onboarded Tiger Analytics skill library, stored as reference only (not auto-loaded or used by workflows) — see its README
hooks/               Safety hook scripts, wired via .claude/settings.json
config/              project.yaml, framework.yaml, integrations.yaml
context/             Repo-owned discovery context (decisions, project-profile) + Neo4j boundary notes
integrations/mcp/    MCP server contract + mock implementation
observability/run-records/  One YAML file per workflow run (state, resumable)
artifacts/           Everything a run produces: validation, migration-plans, generated-code, reports
```

## 8. Extending DB-Kit

- **New workflow**: add a template under `workflows/templates/`, register it in `workflows/registry.yaml`, add a `.claude/commands/db-kit-<name>.md` command following the pattern of the existing three (generate run id → step through template → update run record each step → report).
- **New skill**: add `skills/<category>/<name>.md` (DB-Kit framework skill, referenced by name) (framework skill-docs). Reference-only library skills go in `skills/tiger-library/`; to make one directly invokable, copy it to `.claude/skills/`.
- **New rule**: add under `rules/<category>/`. It will be always-loaded — only put genuine constraints there, not procedures.
- **New hook**: add the script under `hooks/`, wire it into `.claude/settings.json` (use the `update-config` skill), and set its enforcement level in `config/framework.yaml`.

## 9. Known gaps (as of this writing)

- `legacy_to_bronze_silver_migration` has not yet been run end-to-end against a real workspace; expect to iterate on the first live run.
- The Neo4j MCP server is mocked, not real.
- Most of the onboarded Tiger Analytics skill library (`skills/tiger-library/`) targets Databricks/Unity Catalog. Its generic logic is absorbed into DB-Kit's own `skills/*.md` docs (see their "Adapted from" lines); the originals are kept in `skills/tiger-library/` as reference.
