# Skill: Medallion design

**Used by:** Migration Architect Agent.

**Purpose:** Design the Bronze and Silver shape for each in-scope dataset — what gets ingested as-is versus cleaned/conformed, and why.

**Adapted from:** `data-product-orchestrator`'s three-step conceptual/logical/physical design chain (`data_modelling/skills/conceptual_design.md`, `model_design.md`, `physical_design.md`), collapsed to two layers and grounded in discovery/profiling output instead of a BRD, per `rules/medallion/layer-conventions.md` (Gold is out of scope for Phase 1). The DDL rules below are adapted from `skills/tiger-library/data-modeling/references/ddl-generation-rules.md` and `validation-checklist.md`, minus PascalCase/class words, the 28-column STTM CSV, audit-column conventions, DAT/DRD inputs and the common-view step.

## Procedure

For each in-scope dataset (from discovery + profiling):

1. **Bronze shape:** source schema preserved as-is, plus ingestion metadata only (load timestamp, source system, batch/run id). No business logic here — if a profiling finding suggests a transformation is needed, it belongs in Silver, not Bronze.
2. **Silver shape:** apply the business rules identified in discovery; resolve naming to `rules/data-engineering/sql-standards.md` conventions; note every column that changes type, name, or meaning from Bronze, and cite the business rule or convention driving the change.
3. Flag anything that requires a business-logic judgment call neither discovery nor the user has resolved — list it as an open question, do not resolve it silently (spec §3.3, Migration Architect Agent non-goals).

## DDL rules (Bronze and Silver)

Every table design carries a DDL spec that `sql-migration` turns into code. Names are illustrative (`dim_customer`, `dim_product`, `fact_order_lines`); catalog and schema are workflow inputs, never hardcoded.

```sql
CREATE TABLE IF NOT EXISTS {catalog}.{schema}.dim_customer (
    customer_id    STRING     NOT NULL COMMENT 'Business key from the source customer table',
    customer_name  STRING              COMMENT 'Customer display name, trimmed',
    _ingested_at   TIMESTAMP  NOT NULL COMMENT 'Load timestamp of the run that wrote this row',
    _source_table  STRING     NOT NULL COMMENT 'Fully qualified source table of this row'
)
USING DELTA
COMMENT 'Silver customer dimension, one row per customer_id'
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact'   = 'true'
);
```

- Always `CREATE TABLE IF NOT EXISTS` (idempotent; never `ALTER` in generated code) with `USING DELTA`.
- Both `delta.autoOptimize.optimizeWrite` and `delta.autoOptimize.autoCompact` in `TBLPROPERTIES`.
- A `COMMENT` on every column and on the table; column comments come from discovery/profiling/mapping text, not invented.
- `NOT NULL` on primary/merge keys and ingestion metadata. Silver dimension keys are the business key; the fact (`fact_order_lines`) carries its line key plus foreign keys to dimensions, loaded after them.
- **Partitioning by volume** (from profiling row counts): under ~1M rows, do not partition; 1M-100M, partition by a business or load date column; over 100M, date plus a high-cardinality key only if profiling shows it is filtered on. Target roughly 1 GB per partition; under 1 GB total, skip partitioning.
- **Clustering note:** for columns frequently filtered or joined (from the mapping's join keys), record a `ZORDER BY` (run via `OPTIMIZE`) or, where the platform supports it, liquid clustering (`CLUSTER BY`) in the design; liquid clustering replaces partitioning plus ZORDER and is preferred for several high-cardinality filter columns. This is a design note — `OPTIMIZE` is a separate, approved operation.
- Bronze: source columns as-is (landing types preserved or `TRY_CAST` per mapping) plus `_ingested_at`, `_source_table`; same DDL rules apply.

**10-point DDL checklist** (verify before handing the design to `sql-migration`):

1. `CREATE TABLE IF NOT EXISTS` used, never `ALTER`.
2. `USING DELTA` present.
3. `TBLPROPERTIES` include `optimizeWrite` and `autoCompact`.
4. A `COMMENT` on every column, plus a table `COMMENT`.
5. Three-level name built from workflow-input catalog/schema; no hardcoded names.
6. Column names and types follow `rules/data-engineering/sql-standards.md` and match the mapping.
7. Keys are `NOT NULL`; keys and merge keys are listed in the design.
8. Ingestion metadata columns present on Bronze and Silver.
9. Partitioning/clustering chosen from profiled volume, with the volume cited.
10. Dimensions precede facts in load order; every fact foreign key names its dimension.

## Output

Per-dataset Bronze/Silver schema definitions feeding `blueprint.md`, each change traceable to a cited rule or discovery finding.
