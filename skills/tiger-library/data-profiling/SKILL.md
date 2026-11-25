---
name: data-profiling
description: Profile any Delta/Unity Catalog table via Databricks MCP SQL tools with deterministic, concise output and anomaly notes.
---

You are executing a deterministic data-profiling workflow for a Delta/Unity Catalog table using Databricks MCP SQL tools only.

Output folder rule (mandatory):
- Save output as: `Output/DataProfiling/<TableName>_<MMDDYYYY>.md`
- Use `TableName` as the unqualified table name only.
- Date format is always `MMDDYYYY`.

Do not use Databricks REST API. Use MCP SQL tools only.

---

## How to Call This Skill

The only thing you must supply is a way to identify the table. Any of the following are accepted:

| You provide | What happens |
|---|---|
| Fully qualified `catalog.schema.table` | Used as-is — no resolution needed. |
| Partial `schema.table` | If a `catalog` was mentioned earlier in the conversation or only one catalog is accessible, use it. Otherwise ask which catalog. |
| Bare `table` name only | Resolve it: run `SHOW TABLES IN <catalog>.<schema>` (or search `information_schema.tables` within accessible catalogs/schemas) to find matches. If exactly one match is found, use it. If zero or multiple matches are found, list the candidates (or ask for catalog/schema) instead of guessing. |

`environment` is **optional**. Only ask for it if this workspace has more than one Databricks SQL MCP tool (e.g. separate nonprod/prod servers) — see SQL Tool Routing below. If just one Databricks SQL tool is configured, use it directly without asking.

---

## Progressive Disclosure Execution

### Level 1 — Quick Profile (always return)

Return only these deterministic metrics:
- Row count
- Column count
- Duplicate count using all columns (`SELECT COUNT(*) - COUNT(DISTINCT struct(*))`)
- Null % per column (top 15 by null %, tie-breaker by column name)
- Distinct count per column (top 15 by highest distinct count, tie-breaker by column name)

### Level 2 — Distribution & Cardinality (always return)

1. For numeric columns:
- min, max, avg, stddev
- approx percentiles p50, p90, p95, p99

2. For string columns:
- min length, max length, avg length
- top 10 frequent values (excluding null), sorted by count desc then value asc

### Level 3 — Temporal & Freshness (if date/timestamp columns exist)

- Detect candidate temporal columns from data type.
- Return min/max date and coverage span in days.
- Return daily row counts for last 30 days using the best temporal column.

### Level 4 — Quality Rules (always return)

Return deterministic checks:
- Negative values in numeric columns expected to be non-negative (report counts only)
- Blank-string counts for string columns (`trim(col) = ''`)
- Potential key candidates (columns with distinct_count = row_count and null_count = 0)
- Duplicate row sample count (do not print full rows)

---

## Determinism Rules (mandatory)

1. Sort all column-based outputs by:
   1. metric-specific primary order
   2. `column_name ASC` as final tie-breaker
2. Round all decimal metrics to 4 places.
3. Keep output concise:
   - max 15 rows per section unless explicitly requested.
4. Never include non-deterministic samples unless explicitly requested.
5. Use consistent section titles from the template.

---

## SQL Tool Routing

This skill is MCP-server-name-agnostic. Use whichever Databricks SQL MCP tool is available in the current workspace for read-only execution (commonly named like `*_execute_sql_read_only` / `*-execute_sql_read_only`):

- **Single tool configured**: use it for every query, regardless of environment.
- **Multiple environment-scoped tools configured** (e.g. one per nonprod/prod): ask the user which environment to target, then route every query in this run to the matching tool.
- For long-running queries that return a `statement_id`, poll using that same tool family's `*poll_sql_result` tool until the status is no longer `PENDING`/`RUNNING`.

---

## References

- `data-profiling/reference/profiling-reference.md`
- `data-profiling/templates/profiling-queries.sql`
- `data-profiling/templates/profile-output-template.md`

---

## Output Template (mandatory)

Use:
`data-profiling/templates/profile-output-template.md`

Create:
`Output/DataProfiling/<TableName>_<MMDDYYYY>.md`

Populate every section in the template. If a section is not applicable, write `N/A`.

---

## Final Section (mandatory)

End output with:
`## Observations / Anomalies`

Include only high-signal findings:
- Unexpected null spikes
- Extreme cardinality/skew
- Freshness gaps
- Possible key violations
- Out-of-range numeric behavior

Format each item as:
`- [Severity: High|Medium|Low] <short deterministic statement>`
