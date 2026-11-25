# Skill: Quality rule generation

**Used by:** Validation Agent.

**Purpose:** Produce data-quality rules (checks and validations — not-null, uniqueness, range, referential, etc.) for every shortlisted table/column, grounded in its actual profile rather than generic boilerplate.

**Adapted from:** `data-product-orchestrator`'s `data_quality/skills/quality_rule_generation.md`, which generates the same kind of rule set from an STTM. DB-Kit's version is grounded in the profiling skill's output, since the quality-check workflow runs standalone, ahead of any migration mapping. The executable-check shape and expected-result vocabulary are adapted from `skills/tiger-library/databricks-test-runner/SKILL.md`; the parameterized templates below are adapted from `skills/tiger-library/databricks-test-runner/references/SQL_PATTERNS.md` (UT-1, UT-2, UT-3, UT-6, UT-8, DQ-1, DQ-2, DQ-3, DQ-5, DQ-7, PT-1), retargeted from Gold to Bronze/Silver. STTM CSV columns, DAT/DRD sources, audit-column and system-id checks (DQ-4, DQ-6), the Design document and `warning` severity are dropped.

## Procedure

Given the shortlist and each table's profile (row count, null %, distinct count, pk candidates, anomalies) — and, in the migration workflow, the approved mapping and business rules:

1. Produce at least one rule per table/column in scope — no column is skipped.
2. Each rule: `{ rule_id, category, table, column, rule_type, description, severity, rationale, sql, expected }`.
   - `category` is one of `unit` (transformation logic on synthetic rows), `dq` (data checks on real tables), `reconciliation` (cross-layer counts/sums); it is also the parallel-execution batch key.
   - `description` states the concrete check (e.g. "customer_id must be non-null and unique" — not "uniqueness check").
   - `rationale` explains why **this** check matters for **this** column given its profile (a pk-candidate with 0% nulls gets not-null + uniqueness; a small distinct count is a candidate for an allowed-values check; a cast-failure count above zero gets a quarantine-rate check) — never a restatement of `rule_type`.
   - `severity` (`critical`|`high`|`medium`|`low`) reflects real impact if violated.
   - `sql` is one read-only query using three-level names from the run record (never hardcoded), written so a **violation produces rows** wherever possible.
   - `expected` is one of: `zero_rows` (pass if 0 rows); `non_zero` (pass if at least 1 row); `matches_set:{a,b}` (pass if every distinct value is in the set — enums such as status, tier, payment method, region); `column_exists:{c1,c2}`; `type_matches:{c1:type1,c2:type2}`.
3. Include business-rule checks from the mapping/context where present (e.g. a header amount net of discount must reconcile to the sum of its line items).
4. Follow `rules/data-engineering/sql-standards.md` naming conventions.
5. Write the rule set to `artifacts/validation/<project-id>/<run-id>/test-plan.md` as the input to quality-check-execution. This skill produces rule *definitions*; it does not execute them.

## Parameterized test templates

Placeholders in `{braces}` come from the run record (three-level `{table}`), the profile, and the approved mapping. Each template carries an **Applicability** condition: if it is not met, omit the rule entirely (no "skipped" entries). Severity uses DB-Kit's `critical|high|medium|low`. Rules are emitted in the schema above (`category` `dq` unless noted).

| Template | SQL | expected | severity | Applicability |
|---|---|---|---|---|
| **table_exists_non_zero** (UT-1) | `SELECT COUNT(*) AS row_count FROM {table}` | `non_zero` | critical | Always, for every Bronze/Silver table in scope. |
| **column_exists** (UT-2) | `DESCRIBE TABLE {table}` | `column_exists:{c1,...,cN}` | critical | Always; columns = every target column in the mapping (Silver) or the landing/Bronze columns from `describe_table` (Bronze). |
| **type_conformance** (UT-3), one per column | `SELECT typeof({col}) AS actual_type FROM {table} WHERE {col} IS NOT NULL LIMIT 1` | `type_matches:{col:type}` | high | Every column with a declared target type; may batch columns into one `SELECT typeof(c1), typeof(c2) ... LIMIT 1`. Spark types: string, int/bigint/smallint, decimal(p,s), double/float, date, timestamp, boolean. |
| **allowed_values** (UT-6) | `SELECT DISTINCT {col} FROM {table} WHERE {col} IS NOT NULL` | `matches_set:{values}` | high | Column is a finite enum: low distinct count in the profile, or a `CASE ... THEN 'literal'` in the mapping. Skip open-ended columns. |
| **load_strategy** (UT-8) | upsert: `SELECT {merge_keys}, COUNT(*) AS dup_count FROM {table} GROUP BY {merge_keys} HAVING COUNT(*) > 1 LIMIT 10`; append: `SELECT COUNT(*) AS row_count FROM {table}` | upsert `zero_rows` (critical); append `non_zero` (medium) | see left | Mapping states a merge key (upsert) or PK-only (append); omit for delete-insert or unspecified. |
| **pk_not_null** (DQ-1), one per PK column | `SELECT COUNT(*) AS null_count FROM {table} WHERE {pk_col} IS NULL` | `zero_rows` | critical | Mapping/profile declares a primary-key column. |
| **pk_unique** (DQ-2) | `SELECT {pk_cols}, COUNT(*) AS dup_count FROM {table} GROUP BY {pk_cols} HAVING COUNT(*) > 1 LIMIT 10` | `zero_rows` | critical | Mapping/profile declares a primary key (single or composite). |
| **not_null** (DQ-3), one per column | `SELECT COUNT(*) AS null_count FROM {table} WHERE {col} IS NULL` | `zero_rows` | high | Column is declared `NOT NULL` or the profile shows 0% nulls with a mapping/business rule requiring it; exclude PK columns already covered. Columns may be batched with `OR`. |
| **merge_key_not_null** (DQ-5) | `SELECT COUNT(*) AS null_count FROM {table} WHERE {merge_col} IS NULL` | `zero_rows` | critical | Mapping declares a merge key. |
| **custom_business_rule** (DQ-7) | e.g. `SELECT COUNT(*) AS violation_count FROM {table} WHERE {col} <= 0` | `zero_rows` | medium | Only when the mapping/business rules or discovery state an explicit, testable rule. Never invent rules. |
| **ingestion_metadata_populated** (new, replaces Tiger audit-column check) | `SELECT COUNT(*) AS null_count FROM {table} WHERE _ingested_at IS NULL OR _source_table IS NULL` | `zero_rows` | high | Bronze and Silver tables that carry ingestion metadata. |

Direct-mapping, cast and lookup checks (UT-4, UT-5, UT-7) are covered by the synthetic-row unit tests in `sql-migration`; partition checks (PT-1) use `DESCRIBE DETAIL {table}` with `column_exists:partitionColumns` and apply only when the design specifies partition columns. `DESCRIBE`/`EXPLAIN` templates are read-only and accepted by `execute_sql_read_only`.

## CSV export

In addition to `test-plan.md`, write `artifacts/validation/<project-id>/<run-id>/quality-rules.csv` with header `rule_id,table,column,category,expected,severity,sql,evidence_ref,status,detail`. One row per rule; `evidence_ref` points to the profile table/column the rule is grounded in; `status` is `planned` and `detail` empty at generation time (quality-check-execution fills them with pass/fail/blocked). Quote fields containing commas, quotes or newlines; keep `sql` on one line. The CSV is generated from the same rule data as `test-plan.md`: markdown stays primary, hooks keep checking `results.md`, and the CSV carries statistics and rule definitions only, never raw row samples.

## Output

A rule set covering every table/column in scope, each rule citing the profiling evidence it's grounded in. Feeds directly into the quality-check-execution skill.
