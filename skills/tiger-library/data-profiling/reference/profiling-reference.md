# Data Profiling Reference (Delta / Unity Catalog Tables)

## Scope

This reference standardizes concise, deterministic profiling for any Delta/Unity Catalog table using Databricks MCP SQL tools.

## Mandatory conventions

1. Use fully qualified table names: `catalog.schema.table`.
2. Read-only profiling only (`SELECT`, `SHOW`, `DESCRIBE`).
3. Keep outputs deterministic with explicit ordering and fixed rounding (4 decimals).
4. Avoid raw sampling unless explicitly requested.
5. Keep each section concise (maximum 15 rows).

## Suggested profiling sequence

1. `DESCRIBE TABLE <catalog>.<schema>.<table>`
2. Volume and shape metrics (`row_count`, `column_count`, duplicates)
3. Completeness metrics (`null_count`, `null_pct`)
4. Cardinality metrics (`distinct_count`)
5. Type-specific metrics (numeric, string, temporal)
6. Quality checks and key-candidate checks
7. Observations/anomalies summary

## Severity guidance for anomalies

- **High**: likely data quality issue affecting downstream reporting (e.g., freshness gap, key break, extreme null spike).
- **Medium**: unusual pattern that may require validation (e.g., heavy skew, rapid cardinality shift).
- **Low**: informational drift with low immediate impact.
