# Skill: SQL migration (code generation)

**Used by:** Transformation Agent.

**Purpose:** Generate the Bronze/Silver SQL, the notebook that carries it, and the validation scripts implementing an approved `source-to-target-mapping.yaml`, targeting Databricks/Unity Catalog per `rules/target-platform/databricks-medallion-pilot.md`.

**Adapted from:** `data-product-orchestrator`'s `pipeline_engineering/skills/pipeline_code_generation.md` (STTM → real code) — scoped here to one fixed platform for Phase 1. The notebook mapping and load-strategy detection are adapted from `skills/tiger-library/notebook-creation-generic/SKILL.md`, and the synthetic-test technique from `skills/tiger-library/create-unit-test-cases/SKILL.md`, re-pointed at `source-to-target-mapping.yaml` instead of an STTM CSV and stripped of Tiger audit logging, `IS_UNIT_TEST` runner plumbing and org naming. The notebook skeleton below adapts `skills/tiger-library/notebook-creation-generic/references/_generic__table_name___layer__to_gold.py`, and the DDL rules adapt `skills/tiger-library/data-modeling/references/ddl-generation-rules.md` (no `%run`, no audit table or audit columns, no PascalCase).

## Procedure

1. For every `resolved` row, generate the DDL/DML implementing it — idempotent, per `rules/data-engineering/sql-standards.md`. Three-level names come from the run record's resolved landing/Bronze/Silver catalog.schema values (workflow inputs, never hardcoded).
2. For every `unresolved` row, do not generate code — stop at that column and surface it.
3. **One canonical SQL text per target object.** That exact text goes into the notebook's `spark.sql("""...""")` block and is the same text the Validation Agent later passes to `execute_statement`. You never execute anything: no MCP calls, no running the notebook.
4. **Detect the load strategy** from the mapping, and state it in a header comment: merge key present → upsert (`MERGE INTO target USING source ON <merge_key>`); PK only → append; neither → delete-insert (guard with a non-empty-source check). Before an upsert, de-duplicate the source on the merge key and exclude null keys.
5. **Bronze shape:** typed casts (`TRY_CAST`), `_ingested_at`, `_source_table`; rows failing a cast go to a quarantine table with the failed column and raw value. **Silver shape:** dedupe, business-rule enforcement from the mapping, dimensional load order (dimensions before facts), MERGE on PKs.
6. **Notebook structure** (one notebook per target table) — see the skeleton below. No hardcoded credentials, no `%run`, no `%sql` cells for DML.
7. **DDL** for Bronze and Silver tables (including `dim_customer`, `dim_product`, `fact_order_lines` as illustrative Silver tables) follows the rules below.

## Notebook skeleton

Databricks `.py` notebook, cells separated by `# COMMAND ----------`, section headers as `# MAGIC %md`:

1. **Header cell (`%md`):** notebook name, purpose, source table(s), target table (`{catalog}.{schema}.<table>`), load strategy (upsert / append / delete-insert) and the mapping rows implemented (ids).
2. **Widgets:** `dbutils.widgets.text` for `catalog`, `schema` (and the landing/source schema), `run_id`, `project_id`; read with `dbutils.widgets.get`. No defaults that name a real environment.
3. **Variable block:** build three-level names once (`target = f"`{catalog}`.{schema}.dim_customer"`, backticks when a name has hyphens), `LOAD_STRATEGY`, `MERGE_KEYS` (empty list means append), `load_ts`; initialise `rows_written = 0`. Do not print widget values that could be secrets.
4. **Canonical SQL cell:** the single `spark.sql("""...""")` text for the target (explicit columns, `TRY_CAST`, null-key filter, dedupe on merge keys, `_ingested_at`, `_source_table`). This exact text is what the Validation Agent later runs.
5. **Write step:** by strategy: upsert = `MERGE INTO target USING source ON <merge_key>` (`WHEN MATCHED UPDATE`, `WHEN NOT MATCHED INSERT`); append = `INSERT INTO`; delete-insert = non-empty-source guard, then delete and insert in the same cell. Casting failures go to the quarantine table. DDL (`CREATE TABLE IF NOT EXISTS`) runs before the write.
6. **Row-count report:** rows written (and quarantined) read back from the target, printed once; no `display()`.

Failures stop the notebook with a clear message; no audit table is written and no other notebook is called.

## DDL rules

Apply to every `CREATE TABLE` this skill emits, derived from the design in `medallion-design` (which holds the full rule set and 10-point checklist): `CREATE TABLE IF NOT EXISTS` with `USING DELTA`; `TBLPROPERTIES ('delta.autoOptimize.optimizeWrite' = 'true', 'delta.autoOptimize.autoCompact' = 'true')`; a `COMMENT` on every column and on the table; `NOT NULL` on keys and ingestion metadata; partitioning chosen by profiled volume (none under ~1M rows, a date column from 1M to 100M, date plus key above that); a `ZORDER BY`/liquid-clustering recommendation as a comment or follow-up note (not run by the notebook). Run the 10-point checklist from `medallion-design` over each generated DDL and list any failure in the change summary.

## Validation scripts (the other half of this stage)

For each transformed or derived rule, write a test as plain SQL for Stage 6 to run via `execute_sql_read_only`: a `WITH src AS (SELECT * FROM VALUES ...)` CTE of 3–5 synthetic rows in place of the source table, one row per rule branch (normal, null/fallback, boundary, join match, join miss), the transformation applied, and a comparison against an expected value you computed by hand from those rows. Annotate each row with a `-- ->` comment giving its expected output. No TODO placeholders, no vague inequalities, no real data.

## Output

Generated SQL/config/notebooks under `artifacts/generated-code/<project-id>/<run-id>/{bronze,silver,config,tests}/`, plus a short change summary noting any assumption made while translating the mapping into code.
