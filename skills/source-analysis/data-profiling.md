# Skill: Data profiling

**Used by:** Discovery Agent.

**Purpose:** Compute per-column statistics for a shortlisted table so quality-rule generation has real evidence to work from, instead of guessing at what a column contains.

**Adapted from:** `data-product-orchestrator`'s `discovery_analysis/skills/data_profiling_and_analysis.md` (profiles an in-memory CSV sample), and the 4-level progressive-disclosure structure and determinism rules of `skills/tiger-library/data-profiling/SKILL.md`, its output layout (`templates/profile-output-template.md`), query templates (`templates/profiling-queries.sql`) and conventions (`reference/profiling-reference.md`). DB-Kit's version runs real queries through the `db-kit-databricks` MCP server, since this framework prefers deterministic checks over LLM judgment wherever one exists (design principle #5). Tiger's output-folder convention, `MMDDYYYY` file naming and MCP-server-agnostic routing are dropped.

## Inputs

A fully qualified `catalog.schema.table` per shortlisted table. Catalog and schema are workflow inputs resolved for this run (e.g. the landing schema, stored in the run record) — never hardcoded here. If only a bare table name is known, resolve it with `list_tables(catalog, schema)`; zero or multiple matches means list candidates and ask, not guess.

## Procedure

Use `describe_table(catalog, schema, table)` for column names, declared types and nullability (the live schema, never inferred from samples), then run every metric below with `execute_sql_read_only(sql, row_limit)` — actual `COUNT`/`COUNT(DISTINCT ...)`/`SUM(CASE WHEN ... IS NULL ...)` queries, not LLM estimates from a sample. Landing tables may be all-STRING; profile them as declared and, where a column comment names an intended cast, also report how many values would fail it (`TRY_CAST(col AS type) IS NULL AND col IS NOT NULL`).

**Level 1 — Quick profile (always).** Row count; column count; duplicate-row count; null % and distinct count per column; primary-key candidates (100% non-null and 100% distinct).

**Level 2 — Distribution and cardinality (always).** Numeric (or cast-able) columns: min, max, avg, stddev, approximate p50/p90/p99. String columns: min/max/avg length, top 10 values (excluding null) by count desc then value asc. Low-cardinality columns are candidates for allowed-value rules (e.g. a status, tier or region column).

**Level 3 — Temporal and freshness (if date/timestamp columns exist, or STRING columns whose comment/cast says so).** Min/max, coverage span in days, daily row counts for the last 30 days on the best temporal column (e.g. a `_landed_at` load timestamp).

**Level 4 — Quality-rule-shaped anomalies (always).** Counts only: negatives in columns expected non-negative; blank strings (`TRIM(col) = ''`); cast failures (above); orphaned foreign keys against the parent table; duplicate PK values; cross-column reconciliation where a business rule is known (e.g. an order header amount versus the sum of its line items).

## Determinism rules

1. Sort every column-based output by its metric's primary order, then `column_name ASC`.
2. Round decimals to 4 places.
3. Cap each section at 15 rows unless more is requested; never print full duplicate rows.
4. No non-deterministic samples (`TABLESAMPLE`, `RAND()`, unordered `LIMIT`).
5. Only `SELECT`/`WITH`/`DESCRIBE`/`SHOW`/`EXPLAIN` — profiling never writes. If a query fails, record the metric as `blocked` with the error; never fill in a number.

## Output structure (per table)

Write one profile per table with this layout (adapted from `templates/profile-output-template.md`; the Tiger output path and `MMDDYYYY` naming are dropped):

```
# Data Profile: {catalog}.{schema}.{table}
Run date: <date>
## Level 1 - Quick Profile      Row Count / Column Count / Duplicate Row Count; Null % by Column (top 15); Distinct Count by Column (top 15)
## Level 2 - Distribution & Cardinality   Numeric (min,max,avg,stddev,p50,p90,p95,p99); String (min/max/avg length); Top Values (top 10 per key string column)
## Level 3 - Temporal & Freshness         Temporal coverage (min,max,coverage days); Daily volume (last 30 days)
## Level 4 - Quality Rules       Negative counts; blank-string counts; key candidates; duplicate row sample count
## Observations / Anomalies      - [Severity: High|Medium|Low] <statement>
```

Severity: **High** = likely quality issue affecting downstream reporting (freshness gap, key break, extreme null spike); **Medium** = unusual pattern needing validation (heavy skew, cardinality shift); **Low** = informational drift. Sections cap at 15 rows; no raw sampling unless explicitly requested.

## Query templates

Adapted from `templates/profiling-queries.sql`. `{table}` is the three-level name from the run record; generate one `SELECT` per column and `UNION ALL` where noted. `col` is the column name (backtick-quoted when needed).

```sql
DESCRIBE TABLE {table};
SELECT COUNT(*) AS row_count FROM {table};
SELECT COUNT(*) - COUNT(DISTINCT struct(*)) AS duplicate_row_count FROM {table};
-- per column, UNION ALL:
SELECT 'col' AS column_name, SUM(CASE WHEN col IS NULL THEN 1 ELSE 0 END) AS null_count,
       ROUND(100.0 * SUM(CASE WHEN col IS NULL THEN 1 ELSE 0 END) / COUNT(*), 4) AS null_pct FROM {table}
SELECT 'col' AS column_name, COUNT(DISTINCT col) AS distinct_count FROM {table}
-- numeric column:
SELECT 'col', MIN(col), MAX(col), ROUND(AVG(col),4), ROUND(STDDEV(col),4),
       PERCENTILE_APPROX(col,0.50), PERCENTILE_APPROX(col,0.90), PERCENTILE_APPROX(col,0.95), PERCENTILE_APPROX(col,0.99)
FROM {table} WHERE col IS NOT NULL
-- string column:
SELECT 'col', MIN(LENGTH(col)), MAX(LENGTH(col)), ROUND(AVG(LENGTH(col)),4) FROM {table} WHERE col IS NOT NULL
-- top values:
SELECT col AS value, COUNT(*) AS value_count FROM {table} WHERE col IS NOT NULL
GROUP BY col ORDER BY value_count DESC, value ASC LIMIT 10
-- temporal:
SELECT MIN(CAST(col AS DATE)), MAX(CAST(col AS DATE)),
       DATEDIFF(MAX(CAST(col AS DATE)), MIN(CAST(col AS DATE))) AS coverage_days FROM {table} WHERE col IS NOT NULL
-- last 30 days:
SELECT CAST(col AS DATE) AS dt, COUNT(*) AS row_count FROM {table}
WHERE CAST(col AS DATE) >= DATE_SUB(CURRENT_DATE(), 30) GROUP BY CAST(col AS DATE) ORDER BY dt ASC
```

Suggested sequence (from `reference/profiling-reference.md`): schema, volume/shape, completeness, cardinality, type-specific metrics, quality checks and key candidates, observations. Read-only statements only.

## CSV export

In addition to the markdown profile, write `artifacts/validation/<project-id>/<run-id>/profile.csv`: one row per table and column, header `table,column,data_type,row_count,null_count,null_pct,distinct_count,min,max,avg,min_len,max_len,is_key_candidate`. `min`/`max`/`avg` apply to numeric and temporal columns, `min_len`/`max_len` to string columns; leave non-applicable cells empty. `is_key_candidate` is `true` when the column is 100% non-null and 100% distinct. The CSV is generated from the same query results as the markdown: markdown stays primary and hooks keep checking `results.md`. It holds statistics only, never raw row samples or top-value contents. A `blocked` metric is written empty and noted in the markdown.

## Output

Per-table profile: `{ table, row_count, columns: [{ column, null_pct, distinct_count, inferred_type, pk_candidate: bool }], levels: { distribution, temporal, anomalies } }`, cited by table/column in the discovery report and ending with an `Observations / Anomalies` list, each item `[Severity: High|Medium|Low] <short deterministic statement>` (null spikes, extreme skew, freshness gaps, possible key violations, out-of-range values). Feeds directly into quality-rule generation.
