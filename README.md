# DB-Kit

**A repository-based Claude Code framework for governed data-engineering migrations.**

DB-Kit is not a standalone program. It is a set of files — rules, agents, skills, workflow templates, safety hooks, slash commands and MCP connectors — that shape how Claude Code behaves when you do migration work in this repo. You type a `/db-kit-*` command, Claude walks a defined workflow, and every plan, generated notebook, validation result and report lands in the repo as reviewable files.

**Phase 1 (current)** migrates data into a **Databricks medallion architecture**: *source → landing → Bronze → Silver*, against a non-production Unity Catalog workspace.

> Status: Phase 1 pilot, branch `v1-phase1-foundation`. A complete dry-run example is committed under [`artifacts/`](artifacts/) (project `example-project`).

---

## Table of contents

1. [Key ideas](#key-ideas)
2. [Architecture](#architecture)
3. [Workflows and commands](#workflows-and-commands)
4. [Quick start](#quick-start)
5. [Configuration](#configuration)
6. [Source and target support](#source-and-target-support)
7. [The migration workflow in detail](#the-migration-workflow-in-detail)
8. [Safety model (hooks)](#safety-model-hooks)
9. [MCP connectors](#mcp-connectors)
10. [Agents, rules and skills](#agents-rules-and-skills)
11. [Run records and resuming](#run-records-and-resuming)
12. [What a run produces](#what-a-run-produces)
13. [Repository layout](#repository-layout)
14. [Testing](#testing)
15. [Extending DB-Kit](#extending-db-kit)
16. [Known limitations](#known-limitations)
17. [Further reading](#further-reading)

---

## Key ideas

| Principle | How it shows up |
|---|---|
| **Everything is a file** | Rules, agents, workflows and run state are plain Markdown/YAML in git. Nothing hidden, everything reviewable. |
| **Human approval before writes** | The migration workflow stops at a *blueprint approval gate*. Until the approval is recorded in the run record, a hook blocks every Databricks write. |
| **Hooks, not promises** | Safety boundaries (secrets, destructive SQL, production targets, MCP allowlist) are enforced by `PreToolUse` hook scripts, not by asking the model nicely. |
| **Resumable runs** | State lives in `observability/run-records/<run-id>.yaml` and holds *references* to artifacts, so a run can resume in a brand-new session. |
| **Read-only sources** | Azure SQL and PostgreSQL connectors expose no write tool at all; sessions are read-only and SQL is guarded. |
| **Separation of roles** | Five scoped agents (discovery, migration-architect, transformation, validation, review). Only the Validation Agent may execute SQL. |

## Architecture

```
                         ┌──────────────────────────────────────────────┐
  /db-kit-* command ───▶ │  Workflow template (workflows/templates/*.yaml) │
                         └──────────────┬───────────────────────────────┘
                                        │ each step names an agent + skills
              ┌─────────────┬───────────┼────────────┬──────────────┐
              ▼             ▼           ▼            ▼              ▼
          Discovery   Migration-    Transformation  Validation    Review
                      Architect
              │  follow skills/*.md, bound by rules/**/*.md  │
              └─────────────┬────────────────────────────────┘
                            │ every tool call passes through
                            ▼
                  PreToolUse hooks (hooks/**)  ──▶  block / allow
                            │
              ┌─────────────┼───────────────┬──────────────────┐
              ▼             ▼               ▼                  ▼
        db-kit-context  db-kit-azuresql  db-kit-postgres  db-kit-databricks
        (Neo4j, mock)   (read-only)      (read-only)      (read + gated write)
                            │
                            ▼
        artifacts/…  +  observability/run-records/<run-id>.yaml
```

The original architecture diagram is in [`architecture.mmd`](architecture.mmd) (Mermaid) and [`v1-arch.png`](v1-arch.png). The full specification is [`DB-Kit-V1-spec.md`](DB-Kit-V1-spec.md).

## Workflows and commands

Run these inside Claude Code, opened in this repo.

| Command | Workflow | Steps | Approval gate |
|---|---|---|---|
| `/db-kit-help` | — | Prints condensed usage | — |
| `/db-kit-quality-check <scope>` | `data_quality_check` | scope → profile → rule generation → check execution → report | None (read-only) |
| `/db-kit-onboard-to-bronze <scope>` | `source_onboarding_to_bronze` | onboard → DQ check (advisory) → Bronze mapping → Bronze generation → report | None (raw copy, reversible) |
| `/db-kit-migrate [flags]` | `legacy_to_bronze_silver_migration` | discovery → assessment → blueprint → **approval** → generation → documentation → validation → review | **Yes** — blueprint approval |
| `/db-kit-resume <run-id>` | any | Continues a run from its run record | Re-asserts any pending approval |

`<scope>` is a comma-separated table list or a source-system/schema filter.

### `/db-kit-migrate` flags

```
/db-kit-migrate
    [--source databricks:<cat>.<schema> | azuresql:<schema> | postgres:<schema>]
    [--target databricks]
    --landing <catalog>.<schema>              # required
    [--bronze <catalog>.<schema>]             # default: <landing catalog>.bronze
    [--silver <catalog>.<schema>]             # default: <landing catalog>.silver
    [--scope t1,t2]                           # table filter
    [--jdbc-secret-scope <name>]              # azuresql/postgres: Databricks secret scope with JDBC user/password
    [--dry-run]                               # stop after documentation; nothing executed
```

Catalog/schema names are **never** hard-coded in config — you pass them per run.

## Quick start

### Prerequisites

- [Claude Code](https://claude.com/claude-code)
- Python 3.10+ (the hooks and connectors are Python; tests were run on 3.12)
- For a live run: a non-production Databricks workspace with a SQL warehouse, plus optionally a read-only Azure SQL or Azure PostgreSQL source.
- A dry run needs **no Databricks access** — only a source database.

### 1. Build the connector virtualenvs

Each connector has its own venv (they are git-ignored). Repeat for the connectors you need:

```bash
cd integrations/mcp/databricks-sql
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# same for integrations/mcp/azuresql, integrations/mcp/postgres, integrations/mcp/neo4j-context/mock_server
```

### 2. Export credentials

Credentials come **only** from environment variables in the shell that launches Claude Code. Copy and edit the `.env.example` next to each connector (never commit real values, never paste secrets into chat):

| Connector | Variables |
|---|---|
| Databricks | `DB_KIT_DBX_HOST`, `DB_KIT_DBX_HTTP_PATH`, `DB_KIT_DBX_TOKEN` |
| Azure SQL | `DB_KIT_AZSQL_SERVER`, `DB_KIT_AZSQL_DATABASE`, `DB_KIT_AZSQL_USER`, `DB_KIT_AZSQL_PASSWORD` |
| PostgreSQL | `DB_KIT_PG_HOST`, `DB_KIT_PG_DATABASE`, `DB_KIT_PG_USER`, `DB_KIT_PG_PASSWORD` (optional `DB_KIT_PG_PORT`, `DB_KIT_PG_SSLMODE`) |

### 3. Fix paths in `.mcp.json` and `.claude/settings.json`

Both files currently contain **absolute paths** (`/home/kartikmurali/projects/db-kit/...`). If your checkout lives elsewhere, update them. Then launch `claude` from the repo and approve the project MCP servers when prompted.

### 4. Set up your project

Edit `config/project.yaml` (project id/name) and confirm `config/integrations.yaml` marks every connection `production: false`.

### 5. Run something

```text
/db-kit-help

# Safe first run — read-only, nothing written anywhere but artifacts/
/db-kit-quality-check customers,orders,order_items

# Full migration design with no Databricks access (generates code only)
/db-kit-migrate --source postgres:public --landing main.landing --dry-run

# Real migration (stops at the approval gate before any write)
/db-kit-migrate --source azuresql:dbo --landing main.landing \
                --jdbc-secret-scope my-jdbc-scope

# Pick a run back up, same or new session
/db-kit-resume mig-example-project-20261125T062515Z
```

## Configuration

| File | Purpose |
|---|---|
| [`config/project.yaml`](config/project.yaml) | Project id/name, supported source/target platforms, migration scope (`bronze`, `silver`), `production_writes_enabled: false`, policy flags (`require_plan_approval`, `allow_destructive_operations: false`, context budget). |
| [`config/integrations.yaml`](config/integrations.yaml) | Declares each MCP server: status (`mock`/`real`), `allowed_operations` allowlist, `production` flag, connection type. **An MCP tool not declared here is blocked.** |
| [`config/framework.yaml`](config/framework.yaml) | Framework version/phase, hook enforcement levels, resume mechanism, `dynamic_workflows.enabled: false`. |
| [`.mcp.json`](.mcp.json) | How Claude Code launches the four MCP servers. |
| [`.claude/settings.json`](.claude/settings.json) | Wires the `PreToolUse` hooks. |
| [`workflows/registry.yaml`](workflows/registry.yaml) | Registered workflows and versions. |

## Source and target support

| `--source` | Mechanism | Landing |
|---|---|---|
| `databricks:<cat>.<schema>` (default) | Data is already in the landing zone; discovery reads it through `db-kit-databricks`. | None needed |
| `postgres:<schema>` | Azure Database for PostgreSQL via read-only `db-kit-postgres`; Postgres→Spark type mapping. | JDBC-based `landing/load_landing.sql` generated, runs after approval |
| `azuresql:<schema>` | Azure SQL via read-only `db-kit-azuresql`; T-SQL→Spark type mapping. | Same JDBC landing load |

Only `--target databricks` is supported in Phase 1; any other target stops the run. JDBC user/password for the landing load live in a **Databricks secret scope** you create once — DB-Kit asks for the scope and key *names*, never the password. In `--dry-run`, placeholders (`db-kit-demo` / `jdbc-user` / `jdbc-password`) are used and flagged in the blueprint.

## The migration workflow in detail

`legacy_to_bronze_silver_migration` follows the 8-stage model from the spec:

| # | Step | Agent | What happens |
|---|---|---|---|
| 1 | `discovery` | Discovery | Shortlist tables, pull graph context, profile each in-scope table (read-only SQL). Writes a discovery report + `profile.csv`. |
| 2 | `assessment` | Migration Architect | Complexity assessment and risks → `assessment.md`, `risks.md`. |
| 3 | `migration_blueprint` | Migration Architect | Medallion design + source-to-target mapping → `blueprint.md`, `source-to-target-mapping.yaml`. |
| 4 | **approval gate** | You | Run enters `awaiting_approval`. Review, then approve explicitly in chat. The approval is appended to the run record. |
| 5 | `artifact_generation` | Transformation | Generates `landing/`, `bronze/`, `silver/` notebooks and SQL, config, and tests. **Generates only — never executes.** |
| 5 | `documentation` | Transformation | One `docs/<table>_transformation.md` per generated notebook. *(`--dry-run` stops here.)* |
| 6 | `validation` | Validation | Materializes the approved SQL in Databricks (`execute_statement`), then runs row-count, null, key and rule checks. |
| 7 | `review` | Review | Scores the result, lists open issues, writes `migration-report.md`. |
| 8 | release | — | Note only; no production write exists to authorize. |

**Layer conventions** — *Bronze*: typed casts, ingestion metadata, quarantine of bad rows. *Silver*: deduplication, business rules, dimensional model (dim/fact). Gold is out of scope in Phase 1.

If any step cannot complete the run goes to `state: blocked` with the reason recorded; it never guesses or skips.

## Safety model (hooks)

Six `PreToolUse` hooks fire on every matching tool call (not only inside workflows):

| Hook | Matcher | Blocks |
|---|---|---|
| [`block_secrets.py`](hooks/pre-execution/block_secrets.py) | Write, Edit, Bash | Content that looks like a credential/secret |
| [`block_destructive_sql.py`](hooks/pre-execution/block_destructive_sql.py) | Bash, MCP | `DROP`, `TRUNCATE`, `DELETE` without `WHERE`, `ALTER … DROP COLUMN`, … unless approved |
| [`check_production_target.py`](hooks/pre-execution/check_production_target.py) | Bash, MCP | Writes to any connection flagged `production: true` |
| [`check_integration_allowlist.py`](hooks/pre-execution/check_integration_allowlist.py) | MCP | Operations not in a server's `allowed_operations` |
| [`require_blueprint_approval.py`](hooks/validation/require_blueprint_approval.py) | MCP | `execute_statement` unless the run record holds a `migration_blueprint` approval |
| [`require_validation_complete.py`](hooks/validation/require_validation_complete.py) | Write, Edit | Moving to review/report before validation results are complete |

Additionally each connector has its own SQL guard (`tsql_guard.py`, `pg_guard.py`, `sql_guard.py`) that only admits read-only statements on source servers.

**Limitations to know about:** hooks are pattern-based, not semantic. A commit message that merely *mentions* "DROP TABLE" will be blocked — rephrase instead of working around it. Treat a hook block as final.

## MCP connectors

| Server | Status | Access | Tools |
|---|---|---|---|
| `db-kit-databricks` | real | read + one gated write | `list_tables`, `describe_table`, `execute_sql_read_only`, `execute_statement` |
| `db-kit-azuresql` | real | **read-only** (`pymssql`) | `list_tables`, `describe_table`, `execute_sql_read_only` |
| `db-kit-postgres` | real | **read-only** session | `list_tables`, `describe_table`, `execute_sql_read_only` |
| `db-kit-context` | **mock** | Neo4j knowledge graph (retail fixtures) | `list_schema`, `get_entity`, `query_context`, `get_lineage`, `annotate_entity` |

Each lives under [`integrations/mcp/`](integrations/mcp/) with a `CONTRACT.md` (the tool contract) and `README.md`. The Neo4j server is a mock describing a retail dataset (customers, products, orders, order_items) while the knowledge-graph team builds the real one — `integrations/mcp/neo4j-context/CONTRACT.md` is what the real server must satisfy.

`execute_statement(sql, run_id, confirm=true)` is the only write path, is called only by the Validation Agent, and is gated by the blueprint-approval hook.

## Agents, rules and skills

**Agents** ([`agents/`](agents/)) are scoped role contracts — scope, required inputs, permitted tools, output format, evidence requirements, escalation and approval boundaries:
`discovery`, `migration-architect`, `transformation`, `validation`, `review`.

**Rules** ([`rules/`](rules/)) are always-loaded constraints: `core/framework-execution`, `security/safety-boundaries`, `data-engineering/sql-standards`, `medallion/layer-conventions`, `target-platform/databricks-medallion-pilot`. Only genuine constraints belong here, not procedures.

**Skills** ([`skills/`](skills/)) are invocable procedures referenced by name from workflow steps — e.g. `table-shortlisting`, `data-profiling`, `complexity-assessment`, `medallion-design`, `source-to-target-mapping` (plus T-SQL and Postgres→Spark type maps), `sql-migration`, `landing-load`, `quality-rule-generation`, `quality-check-execution`, `reconciliation`, `notebook-documentation`, `migration-review`.

[`skills/tiger-library/`](skills/tiger-library/) is an onboarded Tiger Analytics skill library kept as **reference only** — not auto-loaded and not used by workflows. DB-Kit's own skills cite it via "Adapted from" lines. See its README for a per-skill status table.

## Run records and resuming

Every run has one file: `observability/run-records/<run-id>.yaml` (git-ignored; schema in [`_schema.md`](observability/run-records/_schema.md)). It holds `state`, `current_step`, `input_parameters`, per-step status and timestamps, `output_refs` (paths, never inlined content), `approvals`, and a `completion_summary`.

States: `created → context_loading → discovery → planning → awaiting_approval → executing → validating → reviewing → completed`, plus `failed`, `blocked`, `cancelled`.

Run IDs are prefixed by workflow: `mig-…` (migration), `sob-…` (onboarding), etc. `/db-kit-resume <run-id>` trusts **only** the run record, so it works identically in the same or a new session.

## What a run produces

Under `artifacts/` (example from the committed dry run):

```
artifacts/
├── discovery/<project>/<run-id>/discovery-report.md
├── migration-plans/<project>/<run-id>/
│   ├── assessment.md  risks.md  blueprint.md
│   └── source-to-target-mapping.yaml
├── generated-code/<project>/<run-id>/
│   ├── landing/      register_sources.sql, load_landing.sql
│   ├── bronze/       <table>.py  +  sql/<table>.sql
│   ├── silver/       dim_*.py, fact_*.py, quarantine_rows.py  +  sql/
│   ├── config/run_config.yaml
│   ├── docs/         <table>_transformation.md
│   ├── tests/        silver_rule_tests.sql
│   └── CHANGE_SUMMARY.md
├── validation/<project>/<run-id>/profile.csv   (and quality-rules.csv)
└── reports/<project>/<run-id>/migration-report.md   (full runs only)
```

## Repository layout

```
agents/                 Agent role contracts
rules/                  Always-loaded constraints (core, security, data-engineering, medallion, target-platform)
skills/                 DB-Kit framework skills (+ tiger-library/ reference skills)
workflows/              registry.yaml + templates/*.yaml step definitions
hooks/                  pre-execution/ and validation/ safety hooks
integrations/mcp/       MCP servers: databricks-sql, azuresql, postgres, neo4j-context (mock)
config/                 project.yaml, integrations.yaml, framework.yaml
context/                Repo-owned decisions/ and project-profile/ (graph data lives in Neo4j)
observability/          run-records/ (one YAML per run)
artifacts/              Everything a run produces
tests/                  Hook and SQL-guard unit tests
docs/                   DEVELOPER-HANDBOOK.md, design specs, reference material
.claude/commands/       /db-kit-* slash commands
architecture.mmd, v1-arch.png   Architecture diagram
DB-Kit-V1-spec.md       Full V1 specification
```

## Testing

The tests are pure unit tests for the hooks and SQL guards — no database or workspace required:

```bash
python3 -m unittest discover -s tests -v
```

Covers `block_*`/`check_*`/`require_*` hooks, `tsql_guard`, `pg_guard` and `sql_guard`.

## Extending DB-Kit

- **New workflow** — add a template in `workflows/templates/`, register it in `workflows/registry.yaml`, add `.claude/commands/db-kit-<name>.md` following the existing pattern (generate run id → step through template → update run record each step → report).
- **New skill** — add `skills/<category>/<name>.md` and reference it by name from a workflow step. To make a `tiger-library` skill directly invocable, copy its folder into `.claude/skills/`.
- **New rule** — add under `rules/<category>/` (it will always be loaded).
- **New hook** — add the script under `hooks/`, wire it in `.claude/settings.json`, set its level in `config/framework.yaml`, and add tests in `tests/`.
- **New source type** — add an MCP connector with a read-only guard and `CONTRACT.md`, declare it in `config/integrations.yaml`, add a type-mapping skill, and extend the migrate command/workflow `source` input.

## Known limitations

- Phase 1 targets **Databricks only**; Gold layer is out of scope.
- The Neo4j context server is a **mock**; the real one is in parallel development.
- Full end-to-end live execution against a real workspace is still being iterated on; the committed example is a dry run.
- Hooks are pattern-based and can false-positive on prose.
- `.mcp.json` and `.claude/settings.json` use absolute paths specific to the original checkout.
- Dynamic workflows are disabled (`dynamic_workflows.enabled: false`), deferred post-pilot.
- Context budget enforcement is a soft warning, not a hard limit.

## Further reading

- [`docs/DEVELOPER-HANDBOOK.md`](docs/DEVELOPER-HANDBOOK.md) — day-to-day usage guide
- [`DB-Kit-V1-spec.md`](DB-Kit-V1-spec.md) — full framework specification
- [`docs/superpowers/specs/2026-11-23-db-kit-v1-gap-resolutions-design.md`](docs/superpowers/specs/2026-11-23-db-kit-v1-gap-resolutions-design.md) — Phase 1 design decisions
- [`docs/superpowers/specs/2026-11-24-databricks-medallion-pivot-design.md`](docs/superpowers/specs/2026-11-24-databricks-medallion-pivot-design.md) — Databricks medallion pivot
- [`observability/run-records/_schema.md`](observability/run-records/_schema.md) — run-record schema
- Connector docs: [`databricks-sql`](integrations/mcp/databricks-sql/README.md), [`azuresql`](integrations/mcp/azuresql/README.md), [`postgres`](integrations/mcp/postgres/README.md), [`neo4j-context`](integrations/mcp/neo4j-context/CONTRACT.md)
