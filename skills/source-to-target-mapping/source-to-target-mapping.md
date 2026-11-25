# Skill: Source-to-target mapping

**Used by:** Migration Architect Agent.

**Purpose:** Turn the medallion design into a concrete, column-level source-to-target mapping (STTM) that the Transformation Agent can implement directly, with no remaining ambiguity about which source column feeds which target column.

**Adapted from:** `data-product-orchestrator`'s `data_modelling/skills/model_update.md` (STTM generation for a targeted change) — DB-Kit's version produces the initial STTM for an approved medallion design rather than updating an existing model. The validation pass is adapted from `skills/tiger-library/sttm-validator/SKILL.md` (completeness, key and classification checks), dropping its DRD/DAT spreadsheet column layout, version-history and version-date rules, and Tiger naming rules.

## Procedure

Names are three-level (`catalog.schema.table`), with catalog/schema taken from the run record's resolved landing/Bronze/Silver locations — never hardcoded.

For each target (Bronze or Silver) column:

1. Name the source column(s) it derives from (dataset + column, matching the knowledge-graph entity where one exists).
2. Classify it: `direct` (pass-through), `transformed` (cast, rename, trim, normalize, lookup — one source), `derived` (computed from several columns or tables, e.g. a fact-grain join or reconciled amount), or `no_mapping` (system-generated, e.g. `_ingested_at`, `_source_table`, surrogate keys). State the transformation for every class except `direct`.
3. State the Databricks target type. Landing STRING columns cast to the type their column comment names (DATE, TIMESTAMP, DECIMAL(p,s), INT, BOOLEAN); rows failing a cast go to a quarantine table, not silently NULL.
4. Mark columns with no clear source as unresolved rather than guessing a default.

Table level: record `primary_key`, `merge_key` (the MERGE ON columns), foreign keys, and the load strategy they imply.

## Validation pass (required before the mapping is presented for approval)

Report each finding as `ERROR` (blocks approval), `WARNING`, or `INFO`:

- **Completeness (ERROR):** every target column has a name, type, nullability and classification; no `derived`/`transformed` row lacks its transformation; no `direct` row lacks a source table and column.
- **Source existence (ERROR):** every referenced source table/column exists per `describe_table`.
- **Keys (ERROR):** every target table has a primary key and a merge key; every merge-key column is non-nullable and present in the table; FK columns reference a table also in scope or in the landing schema.
- **Consistency (ERROR/WARNING):** the transformation text matches the classification and the named sources; no duplicate target column; no source column mapped to two target columns without a stated reason; joins for derived columns are stated.
- **Null/blank and dedup handling (WARNING):** stated for every merge-key and business-rule column.
- **INFO:** counts per classification, unresolved count.

## Output

`source-to-target-mapping.yaml`: one row per target column — `{ target_table, target_column, source_table, source_column, classification, transformation, type_mapping, nullable, status: resolved|unresolved }`, plus per-table `{ primary_key, merge_key, foreign_keys, load_strategy }`. Every `unresolved` row and every validation `ERROR` must also appear in `risks.md`; the blueprint is not presented for approval while any `ERROR` remains.
