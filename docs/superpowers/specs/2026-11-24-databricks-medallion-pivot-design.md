# DB-Kit demo pivot: Databricks landing → Bronze → Silver, with the Tiger skill library wired in

## Intent and why

The team demo DB-Kit is being built to pitch is: a source has already landed in a Databricks landing zone (that hop happens outside DB-Kit's scope), and DB-Kit takes it from there — landing zone → Bronze → Silver, full `legacy_to_bronze_silver_migration` workflow (spec §11, all 8 stages), with real business-rule design on the Silver side, not just a raw copy.

**Revision (same day):** the Databricks instance is real, not mocked — a live workspace with a real connection string the user supplies via environment variables. Only the discovery-side **knowledge-graph context** stays mocked (Neo4j, same as before, unrelated to this revision) — that's what "we don't have a context layer yet" referred to. Everywhere below that said "mock Databricks SQL server" now means a **real** connector, and the SQLite-translation compromise from the first builder-check pass is dropped entirely — against a real workspace, the executed statement and the notebook's SQL can genuinely be the same text, which is strictly better than the mock's "two renderings of one mapping" workaround.

This supersedes the Postgres-same-instance direction from earlier in the session (uncommitted, 5 edited files + 1 renamed rule + 1 untracked connector directory — all to be reverted as the first step here, nothing is lost since none of it was committed).

It also resolves something `.claude/skills/README.md` explicitly flagged as deferred: the 20 onboarded Tiger Analytics skills were copied in wholesale but marked "out of scope for Phase 1" because the pilot target was Postgres/Azure SQL. Now that the target is actually Databricks, those skills stop being inert — this design wires the relevant ones in as the real procedural content behind DB-Kit's own skill-docs.

## Goals

- Flesh out `workflows/templates/legacy-to-bronze-silver.yaml` from its current 2-line stub into the full 8-stage workflow per spec §11, targeting Databricks.
- Give DB-Kit a working **real** Databricks SQL/Unity-Catalog connector (live workspace, user-supplied connection string via env vars) for profiling, validation, and Bronze/Silver DDL/DML — no mock query engine needed since the real thing is reachable.
- Absorb the real procedural knowledge from the relevant Tiger Analytics skills into DB-Kit's own `skills/` docs (rules/conventions, not just a pointer to the other file), adapted to DB-Kit's conventions and stripped of PepsiCo/Tiger-org-specific scaffolding that doesn't fit DB-Kit's Project Context Model.
- Keep the workflow's approval gate at Stage 4 (blueprint approval) real and enforced by a hook, not just documented.
- Keep the whole thing demoable end-to-end against the real workspace the user connects, with credentials read only from environment variables, never written into a config file or generated artifact.

## Non-goals

- Gold layer — still explicitly out of Phase 1 scope (`rules/medallion/layer-conventions.md`), regardless of platform.
- Rebuilding `data_quality_check` or `source_onboarding_to_bronze` from scratch — they're written generically enough ("the declared connection", "the db-kit-context MCP server") that pointing `config/project.yaml`/`config/integrations.yaml` at Databricks is enough to carry them along unchanged.
- Carrying over PepsiCo/Tiger-org-specific conventions that don't fit DB-Kit's Project Context Model: DAT/DRD `.xlsx` artifact types, the Tiger audit framework (`log_audit_data`, `cdo_dq_framework`, `NoteBookAuditLog_CL`), NorthStar's `dataengineering/` repository-reference conventions, three-part/PascalCase naming standards. These stay undisturbed inside `.claude/skills/` (still available to invoke standalone) but are not copied into DB-Kit's own skill-docs.

## Anti-goals (would make this a failure even if it "works")

- A demo that silently fabricates query results instead of actually running something deterministic — violates design principle #5 (deterministic checks preferred) and "no fabricated facts." More load-bearing than before: this is now a **real** workspace, so a fabricated result isn't just a demo flaw, it's a false claim about real data.
- Skill-docs that just say "go read `.claude/skills/X/SKILL.md`" with no adaptation — that's Approach A, which the user explicitly rejected in favor of actually copying and editing the knowledge in.
- Breaking the established "every workflow step cites a `skills/` doc, never `.claude/skills/` directly" convention.
- Any generated DDL/DML running against the real workspace without going through the Stage-4 approval gate and the existing safety hooks — those hooks stop being a "backstop that's never tripped" (as `check_production_target.py`'s own docstring currently says) and become the thing actually standing between a generated statement and a real write.

## Constraints

- Real Databricks workspace and credentials — read only from environment variables (`DB_KIT_DBX_*`, see §3), never written into a config file, generated artifact, or passed in chat.
- Preserve prior Milestone-0 architecture decisions: the Neo4j/MCP discovery-knowledge boundary, the run-record resume pattern, the rules/skills/agents ownership split, the hook enforcement levels in `config/framework.yaml`.
- Keep the demo narrative coherent where it's still mocked: the Neo4j knowledge-graph context continues to use the existing `customers`/`orders`/`order_items`/`orders_summary` dataset (`integrations/mcp/neo4j-context/mock_server/fixtures.json`, with a real business rule — `order_total` must equal the sum of line items). Whether the real landing-zone catalog/schema the user connects to actually contains matching tables is an open item (below) — the workflow should discover what's really there, not assume it matches the mock's fixture names.

## Approach (decided in conversation, recorded here)

Three ways to wire in the Tiger skills were considered:
- **A — Light wiring:** leave Tiger skills standalone, DB-Kit's own skill-docs unchanged. Rejected — doesn't make them load-bearing, which was the explicit ask.
- **B — Thin delegation:** DB-Kit skill-docs become pointers telling the agent to go follow the matching `.claude/skills/*/SKILL.md`. Rejected by the user ("copy them... edit that to make it work for us") — the knowledge gets absorbed and adapted, not referenced.
- **C — Deep absorption (chosen):** rewrite the relevant DB-Kit `skills/*.md` docs so their *procedure* is the adapted Tiger-skill content — deterministic rules, status vocabularies, detection heuristics — translated into DB-Kit's own conventions (artifact paths, `source-to-target-mapping.yaml` fields, the `db-kit-databricks` MCP tool names, pass/fail/blocked vocabulary). Workflow steps keep citing DB-Kit's own `skills/` docs, preserving the existing traceability convention; each rewritten doc keeps the existing "Adapted from: ..." citation pattern already used for the `data-product-orchestrator` adaptations.

## Design

### 1. Revert the Postgres-same-instance work

First action, mechanical: `git checkout` the 5 modified files, `git mv` the rule file back, remove `integrations/mcp/postgres-sql/` (untracked, nothing lost). Confirmed superseded by this conversation's pivot.

### 2. Platform configuration

`config/project.yaml`:
```yaml
platform:
  source:
    - type: databricks
      role: landing_zone
      environment_tag: non-production   # CONFIRM with user — see "Open items"
      catalog: null    # fill in: the real landing-zone catalog name
      schema: null      # fill in: the real landing-zone schema name
  target:
    type: databricks
    environment_tag: non-production   # CONFIRM with user — see "Open items"
    catalog: null      # fill in: same or different catalog, per the real workspace layout
    bronze_schema: bronze
    silver_schema: silver
```

`config/integrations.yaml`: replace the (reverted) `db-kit-postgres` entry and `connections.*` block with:
```yaml
mcp:
  db-kit-databricks:
    purpose: Real Databricks SQL / Unity Catalog connector — profiling, validation execution, Bronze/Silver DDL/DML
    provider: databricks
    status: real   # live workspace, user-supplied connection string
    implementation: integrations/mcp/databricks-sql
    contract: integrations/mcp/databricks-sql/CONTRACT.md
    connection: env_vars   # DB_KIT_DBX_HOST/HTTP_PATH/TOKEN/CATALOG -- see integrations/mcp/databricks-sql/.env.example. Never put credentials in this file.
    production: false   # CONFIRM with user before this ships — see "Open items"
    allowed_operations:
      - list_tables
      - describe_table
      - execute_sql_read_only
      - execute_statement

connections:
  source:
    type: databricks
    role: landing_zone
    environment_tag: non-production   # CONFIRM with user
    production: false   # CONFIRM with user
  target:
    type: databricks
    environment_tag: non-production   # CONFIRM with user
    production: false   # CONFIRM with user
```

`rules/target-platform/`: rename (again) to `rules/target-platform/databricks-medallion-pilot.md`, covering: Unity-Catalog three-level naming (`catalog.schema.table`), Delta table conventions (no cross-engine type mapping needed since generation and execution both use Databricks SQL, so no dialect translation), all real SQL execution goes through `db-kit-databricks`, generated notebooks follow the coding standards absorbed from `docs/reference/tiger-copilot-instructions.md` (4-space indent, snake_case tables/columns, capitalized SQL keywords, CTEs for complex queries, no `SELECT *`).

Update the same cross-references touched during the Postgres pivot (`agents/migration-architect.md`, `agents/transformation.md`, `rules/data-engineering/sql-standards.md`, `skills/source-to-target-mapping/source-to-target-mapping.md`, `skills/sql-migration/sql-migration.md`) to point at the new rule file and Databricks framing instead of Postgres same-instance.

### 3. The connector: `integrations/mcp/databricks-sql/`

A real MCP server (same `mcp.server.mcpserver.MCPServer` library as the Neo4j mock) wrapping the `databricks-sql-connector` Python package against the user's live workspace. No fixtures, no query-engine stand-in — every call hits the real SQL warehouse.

**Connection:** environment variables only, never a config file: `DB_KIT_DBX_HOST` (workspace hostname), `DB_KIT_DBX_HTTP_PATH` (SQL warehouse HTTP path), `DB_KIT_DBX_TOKEN` (personal access token), `DB_KIT_DBX_CATALOG` (default catalog). Documented in `.env.example` (gitignored `.env` for real values), `requirements.txt` (`mcp`, `databricks-sql-connector`), and a dedicated venv like the Neo4j mock's. The `block_secrets.py` hook already catches a token literal being written into a file or command.

Tools:
- `list_tables(catalog: str, schema: str) -> dict` — `SHOW TABLES IN catalog.schema`.
- `describe_table(catalog: str, schema: str, table: str) -> dict` — columns, types, nullability, primary-key candidates (via `information_schema` / `DESCRIBE`).
- `execute_sql_read_only(sql: str, row_limit: int = 1000) -> dict` — rejects anything not starting `SELECT`/`WITH`/`DESCRIBE`/`SHOW`/`EXPLAIN` (defense in depth, same rule `databricks-test-runner` already states), returns columns/rows/row_count/truncated.
- `execute_statement(sql: str, run_id: str, confirm: bool = False) -> dict` — DDL/DML (`CREATE SCHEMA IF NOT EXISTS`, `CREATE TABLE ... AS SELECT`, `MERGE INTO`). Requires `confirm: true`; gated by hooks (below) keyed off `run_id` so the Stage-4 approval actually blocks execution. Called by the **Validation Agent**, not the Transformation Agent.

**Execution integrity (simplified by going real):** the real SQL engine runs real Databricks/Delta SQL, so the earlier two-renderings workaround is dropped. `sql-migration` produces one canonical statement per target object; that exact text is both embedded in the generated notebook's `spark.sql("""...""")` block and passed to `execute_statement` — what Stage 7 reviews is literally what ran. The PySpark notebook wrapper around it (widgets, `DeltaTable` calls) is *not* what executes through the connector — only the SQL does, and the contract says so plainly rather than implying the notebook itself ran.

**No seeded data.** Profiling and validation run against whatever is really in the landing zone. The intentional-DQ-issue fixture idea is dropped; the Neo4j mock's `rule-order-total-check` business rule remains the mock context's input, and whether the real tables contain a matching violation is whatever the data says.

### 4. Hooks

Two changes, both generalizations rather than new concepts:

- `block_destructive_sql.py` and `check_production_target.py` currently only scan `tool_input.command` (Bash). Generalize both to scan every string value in `tool_input` (the same `extract_text` helper `block_secrets.py` already uses), so a `sql` parameter on an `mcp__db-kit-databricks__*` call is covered too. Add both to the `mcp__.*` matcher in `.claude/settings.json` alongside the existing `check_integration_allowlist.py`.
- New hook `hooks/validation/require_blueprint_approval.py` (workflow-state gate, mechanism type C per the gap-resolutions design doc): matches `mcp__db-kit-databricks__execute_statement`. Reads `tool_input.run_id`, loads `observability/run-records/<run_id>.yaml`, and blocks unless an `approvals` entry exists for stage `migration_blueprint`. This is Stage 4 (spec §11) actually enforced, not just documented — the same pattern already proven for `require_validation_complete.py`.

**Who calls `execute_statement` (resolved after builder-check):** the **Validation Agent**, at the start of Stage 6 — not the Transformation Agent at the end of Stage 5. `agents/transformation.md` has an existing, deliberately-written Milestone-0 non-goal ("does not execute anything against a real connection") with no MCP tool access; this design does not touch it. Instead, `agents/validation.md` gains `db-kit-databricks` (`execute_statement` + `execute_sql_read_only`) as a permitted tool, consistent with its existing role of running real checks. Stage 6 therefore opens by materializing the approved artifacts against the real workspace, then immediately validates what it just created — matching spec §11 Stage 6's framing as where real checks run against real data, and keeping Transformation Agent's safety invariant fully intact.

Also: all hook commands in `.claude/settings.json` switch to absolute paths (`/home/kartikmurali/projects/db-kit/hooks/...`) instead of relative ones — a real bug surfaced this session (a working-directory drift made every relative-path hook unresolvable, deadlocking Bash/Write/Edit entirely). Unrelated to Databricks, but fixed as part of this pass since it's touching `.claude/settings.json` anyway.

### 5. Workflow: `workflows/templates/legacy-to-bronze-silver.yaml`

Full rebuild from the 2-line stub, one step per spec §11 stage (steps map 1:1 to stages; the approval checkpoint is a gate between steps, not a step itself; Stage 8 is a closing note, not a step — no production write exists to authorize):

| Step id | Spec stage | Agent | DB-Kit skill(s) | Tiger-skill content absorbed into it |
|---|---|---|---|---|
| `discovery` | 1 | discovery | `project-discovery/table-shortlisting`, `repository-analysis/repository-analysis`, `source-analysis/data-profiling` | `data-profiling`'s 4-level progressive disclosure + determinism rules |
| `assessment` | 2 | migration-architect | **new:** `migration-assessment/complexity-assessment.md` | — (no close Tiger equivalent; written fresh) |
| `migration_blueprint` | 3 | migration-architect | `medallion-design/medallion-design`, `source-to-target-mapping/source-to-target-mapping` | `sttm-validator`'s completeness checklist, folded in as a pre-approval validation pass |
| *(approval checkpoint)* | 4 | — | — | `require_blueprint_approval.py` hook enforces it |
| `artifact_generation` | 5 | transformation | `sql-migration/sql-migration` | `notebook-creation-generic`'s STTM→notebook mapping table + load-strategy detection; `create-unit-test-cases`'s synthetic-row-with-computed-expected-values technique, for the "generate validation scripts/tests" part of this stage |
| `validation` | 6 | validation | `data-quality/quality-rule-generation`, `data-quality/quality-check-execution`, `reconciliation/reconciliation` | `databricks-test-runner`'s RED/GREEN/SKIPPED status model and parallel-by-module subagent dispatch; its pass/fail criteria vocabulary (`zero_rows`/`non_zero`/`matches_set`/`column_exists`/`type_matches`) folded into `quality-rule-generation` |
| `review` | 7 | review | `migration-review/migration-review` | A trimmed, generic subset of `code-review-tiger`'s review categories (Delta/Schema, Data Quality, Unity Catalog, Observability, Cell structure) minus its Tiger-audit-framework-specific checks; `code-documentation`'s "don't invent values" discipline |
| *(human release decision)* | 8 | — | — | Documented note only — no production write exists to authorize, matching existing `production_writes_enabled: false` |

`approval_gates`: one, before `artifact_generation`, enforced by `require_blueprint_approval.py`.

### 6. Skill-doc rewrites (where the real adaptation work is)

Each gets an "Adapted from" line pointing at the specific `.claude/skills/<name>/SKILL.md`, same citation style already used for `data-product-orchestrator` adaptations elsewhere in `skills/`:

- `skills/source-analysis/data-profiling.md` — add the 4-level structure (quick profile / distribution & cardinality / temporal & freshness / quality-rule-shaped anomalies) and the determinism rules (sort order, rounding, row caps), re-pointed at `db-kit-databricks`'s `execute_sql_read_only`.
- **New** `skills/migration-assessment/complexity-assessment.md` — Stage 2 has no existing DB-Kit skill or close Tiger equivalent; written fresh per spec §11 Stage 2 bullets (complexity, dependency risk, ambiguous logic, volume/incremental considerations, platform compatibility, migration-order recommendation).
- `skills/source-to-target-mapping/source-to-target-mapping.md` — add a validation pass before the mapping is considered ready for approval, adapted from `sttm-validator`'s checklist (completeness, PK/FK/merge-key consistency, derived-vs-direct-vs-no-mapping classification), generalized away from its org-agnostic-by-design content (it already says it must stay generic).
- `skills/sql-migration/sql-migration.md` — add the STTM-to-notebook structural mapping and load-strategy auto-detection (merge-key present → upsert, PK-only → append, neither → delete-insert) from `notebook-creation-generic`, re-pointed at `source-to-target-mapping.yaml` fields instead of a separate STTM CSV; add the synthetic-test-data technique from `create-unit-test-cases` for the "generate validation scripts" half of Stage 5.
- `skills/data-quality/quality-rule-generation.md` and `quality-check-execution.md` — adopt `databricks-test-runner`'s status vocabulary (map RED/GREEN/SKIPPED onto DB-Kit's existing fail/pass/blocked) and its pass/fail criteria patterns; adopt the parallel-dispatch-by-module idea (one subagent per rule category) as an optional execution strategy for larger rule sets.
- `skills/migration-review/migration-review.md` — add a trimmed review-category checklist (Delta/schema conventions, DQ/row validation, Unity Catalog naming, observability/logging hygiene, notebook cell structure) and a 0–100 compliance score, adapted from `code-review-tiger` with every Tiger-audit-framework-specific check (`log_audit_data`, `cdo_dq_framework`, PL_Name widgets) dropped since DB-Kit doesn't generate against that framework.

### 7. Command

New `.claude/commands/db-kit-migrate.md`, following the existing `db-kit-onboard-to-bronze.md` pattern: generates a `mig-`-prefixed run id, steps through the 8 steps above, pauses at the approval gate (presents the blueprint, requires explicit approval before calling `execute_statement`), handles `blocked`, reports to `artifacts/reports/<project-id>/<run-id>/migration-report.md`. `workflows/registry.yaml` already lists `legacy_to_bronze_silver_migration` — no change needed there.

## What's left to the builder

- Exact wording of the "Adapted from" sections and how much of each Tiger skill's detail survives vs. gets summarized — guided by the principle above (keep generic/deterministic logic, drop org-specific scaffolding).
- Whether `complexity-assessment.md`'s risk register is a markdown table or a small structured list — markdown table, consistent with every other DB-Kit skill's output format.

## Decisions from your last message (supersede anything above that conflicts)

1. **Non-production confirmed:** it's a Databricks test catalog, so `production: false` / `environment_tag: non-production` are set.
2. **Catalog and schema are workflow inputs, not config.** `config/project.yaml` holds no catalog or schema names. `/db-kit-migrate` takes `--landing <catalog>.<schema>` and optional `--bronze <catalog>.<schema>` / `--silver <catalog>.<schema>`. Defaults, which are my call: Bronze and Silver go in the landing catalog, in schemas named `bronze` and `silver`. The run record stores the resolved names, and the Validation Agent creates the schemas with `CREATE SCHEMA IF NOT EXISTS` if they're missing. `DB_KIT_DBX_CATALOG` is dropped as a required variable, so the connector needs only host, HTTP path and token. Every tool call takes explicit catalog and schema.
3. **Table names vary too.** Nothing hardcodes `retail_dev.landing.raw_*`. Discovery lists whatever is in the landing schema. The Bronze name is the landing name with a `raw_` prefix stripped (my call, overridable in the blueprint).
4. **Sample dataset is your retail schema:** `raw_customers`, `raw_products`, `raw_orders`, `raw_order_items`. Every column is STRING, plus `_landed_at`, with PK/FK constraints and comments that name the intended Bronze casts. The Neo4j mock fixtures are rewritten to describe this retail model:
   - Entities and the FK lineage orders -> customers, items -> orders, items -> products.
   - Business rules: `gross_amount - discount_amount` must reconcile to the sum of `quantity * unit_sold_price`; `loyalty_tier` is in {Bronze, Silver, Gold, Platinum}; `order_status` is in {COMPLETED, RETURNED, CANCELLED}; `payment_method` is in {UPI, CARD, CASH}; `region` is in {North, South, East, West}; email is nullable but flagged.
   - The mock stays keyed to the table's base name (`customers`, ...), so it still matches when the catalog or schema changes.
5. **Medallion shape this implies (proposal):**
   - Bronze casts the STRING columns to the types the column comments name (DATE, TIMESTAMP, DECIMAL(10,2), INT, BOOLEAN), keeps `_landed_at`, adds `_ingested_at` and `_source_table`, and quarantines rows that fail a cast.
   - Silver conforms and deduplicates, enforces the business rules, and builds a joined `order_lines` fact plus customer and product dimensions.
   - Loads use MERGE keyed on the PKs.

## Open items for you

1. Is the proposed catalog-as-input shape (`--landing <catalog>.<schema>`, Bronze and Silver defaulting to the landing catalog) what you want?
2. Should Silver be dimensional (dim_customer, dim_product, fact_order_lines), or a conformed one-table-per-entity cleanse? I'd pick the dimensional one for the demo because it shows off the business rules better.
3. The token goes in `DB_KIT_DBX_TOKEN` and the host and HTTP path in their own variables, set on your machine. Don't paste them here.
