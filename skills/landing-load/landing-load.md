# Skill: landing-load

**Purpose:** Generate the SQL that copies a relational source (Azure SQL or Azure Database for PostgreSQL) into the Databricks landing schema (used only when the run's source type is `azuresql` or `postgres`).

**Adapted from:** none — no Tiger equivalent. Written for DB-Kit's `legacy_to_bronze_silver_migration` workflow (step `landing_load`).

## When it applies

`input_parameters.source.type` is `azuresql` or `postgres`. For a `databricks` source the data is already in landing and this skill is skipped.

## Inputs

- Approved `source-to-target-mapping.yaml` (landing section: source schema/table, selected columns, type mapping per `skills/source-to-target-mapping/tsql-to-spark-type-mapping.md`).
- Run inputs: Azure SQL host/database (from the connection env var names only — never values), landing `<catalog>.<schema>`, Databricks secret scope and key names holding the JDBC user/password.

## Procedure

1. **Rules.** One canonical SQL text per statement; the same text goes into the generated notebook and later into `execute_statement` (Validation Agent). You never execute anything.
2. **Register the JDBC source table** — one statement per source table, persistent metadata only (no data moves). Name: `<landing_catalog>.<landing_schema>._jdbc_src_<table>`:
   ```sql
   CREATE TABLE IF NOT EXISTS <catalog>.<schema>._jdbc_src_<table>
   USING sqlserver
   OPTIONS (
     host '<server>.database.windows.net', port '1433', database '<database>',
     dbtable '<source_schema>.<source_table>',
     user secret('<scope>', '<user_key>'), password secret('<scope>', '<password_key>')
   );
   ```
   Never write a literal user or password. `<server>`/`<database>` come from the run inputs.

   **PostgreSQL source** (`source.type == postgres`): use the generic JDBC source instead (credentials still only via `secret()`):
   ```sql
   CREATE TABLE IF NOT EXISTS <catalog>.<schema>._jdbc_src_<table>
   USING JDBC
   OPTIONS (
     url 'jdbc:postgresql://<host>:5432/<database>?sslmode=require',
     dbtable '<source_schema>.<source_table>',
     user secret('<scope>', '<user_key>'), password secret('<scope>', '<password_key>')
   );
   ```
   Type mapping comes from `skills/source-to-target-mapping/postgres-to-spark-type-mapping.md`. Use the `db-kit-postgres` server for source-side reconciliation.
3. **Copy into landing** — one statement per table, explicit column list (no `SELECT *`), plus `_landed_at`:
   ```sql
   CREATE OR REPLACE TABLE <catalog>.<schema>.raw_<table> AS
   SELECT <col1>, <col2>, ..., current_timestamp() AS _landed_at
   FROM <catalog>.<schema>._jdbc_src_<table>;
   ```
   Landing is a faithful copy: Spark types come from the JDBC read; business casting is Bronze's job.
4. **Order:** parents before children (use the FK order from the blueprint). Register all `_jdbc_src_*` tables first, then the copies.
5. **Primary keys:** after the copy, add the source PK/FK as informational constraints only if the mapping lists them (`ALTER TABLE ... ADD CONSTRAINT ... PRIMARY KEY (...)` requires NOT NULL columns; skip with a note if a column is nullable).

## Validation hooks for this step (Stage 6)

Reconciliation per table: `COUNT(*)` of `raw_<table>` equals `COUNT(*)` of `_jdbc_src_<table>` and of the source (via `db-kit-azuresql.execute_sql_read_only` or `db-kit-postgres.execute_sql_read_only`, by source type); per-column null counts match; for each numeric column, `SUM` matches within the type's precision. Any mismatch is `fail`; an unreadable source or JDBC error is `blocked` with the real error text.

## Known risk — record, don't hide

The SQL warehouse must be able to reach the source server over the network (firewall/private link) and support the `sqlserver` (Azure SQL) or `JDBC` with the PostgreSQL driver (Postgres) data source. If the registration statement fails, mark `landing_load` `blocked`, record the exact error, and offer the fallback: generate a Databricks notebook under `artifacts/generated-code/<project-id>/<run-id>/landing/` that the user runs themselves on a cluster, using the same table list and secret names. Never work around a failure by embedding credentials.

## Output

`artifacts/generated-code/<project-id>/<run-id>/landing/{register_sources.sql,load_landing.sql}` (statements in execution order, separated by blank lines with a header comment per table), plus a change summary.
