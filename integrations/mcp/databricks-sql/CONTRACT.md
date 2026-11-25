# db-kit-databricks MCP server — tool contract

A **real** connector: every call hits the live Databricks SQL warehouse configured by environment variables. There is no mock variant. The workspace is a non-production test catalog (`config/integrations.yaml`).

## Connection (environment variables only)

| Variable | Required |
|---|---|
| `DB_KIT_DBX_HOST` | yes — workspace hostname |
| `DB_KIT_DBX_HTTP_PATH` | yes — SQL warehouse HTTP path |
| `DB_KIT_DBX_TOKEN` | yes — personal access token |

Catalog and schema are **not** configured: every tool takes them as arguments (they are workflow inputs). See `.env.example`, `README.md`.

## Tools

### `list_tables(catalog, schema) -> {tables: [string], error?: string}`
`SHOW TABLES`. Identifiers must match `[A-Za-z0-9_-]+`.

### `describe_table(catalog, schema, table) -> {columns: [{column, data_type, is_nullable, comment, ordinal_position}], primary_key_columns: [string], error?: string}`
Via `<catalog>.information_schema`. Unknown table returns an `error`, not an exception.

### `execute_sql_read_only(sql, row_limit=1000) -> {status, columns, rows, row_count, truncated}`
Accepts exactly one `SELECT`/`WITH`/`DESCRIBE`/`SHOW`/`EXPLAIN` statement; anything else returns `{status: "rejected", reason}`. `row_limit` 1–100000. Failures return `{status: "failed", error}` with the real message.
Used by: data-profiling, quality-check-execution, reconciliation.

### `execute_statement(sql, run_id, confirm=false) -> {status: "executed"|"rejected"|"failed", rows_affected, error}`
One DDL/DML statement per call. Safety, in order:
1. `confirm` must be `true`, else rejected before touching the warehouse.
2. `hooks/pre-execution/block_destructive_sql.py` and `check_production_target.py` run on the call (they scan every `tool_input` string).
3. `hooks/validation/require_blueprint_approval.py` blocks it unless `observability/run-records/<run_id>.yaml` has an `approvals` entry for stage `migration_blueprint`.
Called only by the Validation Agent at the start of Stage 6. The SQL text is exactly what the generated notebook contains.

## Not covered
Connection pooling/retry (one short-lived connection per call), multi-statement transactions, any operation not in `allowed_operations`.
