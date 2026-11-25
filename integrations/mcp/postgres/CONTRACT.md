# db-kit-postgres MCP server — tool contract

A **real, read-only** connector to an Azure Database for PostgreSQL (psycopg). No mock variant and **no write tool exists** — DB-Kit reads this source; data reaches Databricks through the approved `landing_load` statements executed on the Databricks side.

## Connection (environment variables only)
`DB_KIT_PG_HOST`, `DB_KIT_PG_DATABASE`, `DB_KIT_PG_USER`, `DB_KIT_PG_PASSWORD` (optional `DB_KIT_PG_PORT`, default 5432; `DB_KIT_PG_SSLMODE`, default `require`). See `.env.example`. The session is opened read-only (`conn.read_only = True`, so the server itself rejects writes), every connection is rolled back and never committed, and `pg_guard.py` additionally accepts only a single SELECT/WITH. Use a database user with read-only grants for defence in depth.

## Tools
- `list_tables(schema) -> {tables: [string], error?}` — base tables from `INFORMATION_SCHEMA.TABLES`.
- `describe_table(schema, table) -> {columns: [{column, data_type, char_max_length, numeric_precision, numeric_scale, is_nullable, ordinal_position, udt_name}], primary_key_columns, foreign_keys: [{column, references_schema, references_table, references_column}], error?}`.
- `execute_sql_read_only(sql, row_limit=1000) -> {status: ok|rejected|failed, columns, rows, row_count, truncated}` — exactly one `SELECT`/`WITH` statement. The guard (`pg_guard.py`) scans every token and rejects `INTO`, DML, DDL, `COPY`/`CALL`/`DO`, side-effect functions (`set_config`, `nextval`, `dblink`, `pg_read_file`...) and stacked statements (string literals incl. `$$` quoting, comments and "quoted" identifiers are ignored).

Identifiers (schema/table) must match `[A-Za-z0-9_-]+`. Used by: discovery, data-profiling, reconciliation (source-side counts).
