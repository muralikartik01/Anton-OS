# db-kit-azuresql MCP server — tool contract

A **real, read-only** connector to an Azure SQL Database (pymssql/TDS). No mock variant and **no write tool exists** — DB-Kit reads this source; data reaches Databricks through the approved `landing_load` statements executed on the Databricks side.

## Connection (environment variables only)
`DB_KIT_AZSQL_SERVER`, `DB_KIT_AZSQL_DATABASE`, `DB_KIT_AZSQL_USER`, `DB_KIT_AZSQL_PASSWORD` (optional `DB_KIT_AZSQL_PORT`, default 1433). See `.env.example`. pymssql has no read-only connection flag, so read-only is enforced by `tsql_guard.py` (SELECT/WITH only) plus a rollback and no commit on every connection. Use a database user with only `db_datareader` for defence in depth.

## Tools
- `list_tables(schema) -> {tables: [string], error?}` — base tables from `INFORMATION_SCHEMA.TABLES`.
- `describe_table(schema, table) -> {columns: [{column, data_type, char_max_length, numeric_precision, numeric_scale, is_nullable, ordinal_position}], primary_key_columns, foreign_keys: [{column, references_schema, references_table, references_column}], error?}`.
- `execute_sql_read_only(sql, row_limit=1000) -> {status: ok|rejected|failed, columns, rows, row_count, truncated}` — exactly one `SELECT`/`WITH` statement. The guard (`tsql_guard.py`) scans every token and rejects `INTO`, `EXEC`, DML, DDL and stacked statements (string literals, comments and `[bracketed]` identifiers are ignored).

Identifiers (schema/table) must match `[A-Za-z0-9_-]+`. Used by: discovery, data-profiling, reconciliation (source-side counts).
