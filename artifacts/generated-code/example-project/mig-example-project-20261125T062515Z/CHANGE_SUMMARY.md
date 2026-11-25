# Change summary — mig-example-project-20261125T062515Z (dry run)

Generated from the approved `source-to-target-mapping.yaml` (approval recorded in the run record; OQ1 option (a)). **Nothing was executed**: no MCP write, no notebook run, no Databricks access.

## Contents
- `landing/register_sources.sql`, `landing/load_landing.sql` — JDBC registration + full-reload copy of `raw_dump.raw_*` into landing.
- `bronze/{customers,products,orders,order_items}.py` + `bronze/sql/*.sql` — as-is append with `_ingested_at`, `_source_table`.
- `silver/{quarantine_rows,dim_customer,dim_product,fact_orders,fact_order_lines}.py` + `silver/sql/*.sql`.
- `config/run_config.yaml` — widget values and execution order. `tests/silver_rule_tests.sql` — 5 synthetic-row rule tests (not run). `docs/` — one document per notebook (9).
- Each `sql/<table>.sql` is the notebook's statements with placeholders resolved; this is the text the Validation Agent would pass to `execute_statement`, one statement at a time.

## Assumptions and small clarifications made while generating (none changes scope)
1. **JDBC placeholders:** scope `db-kit-demo`, keys `jdbc-user`/`jdbc-password`, and `<DB_KIT_PG_HOST>` / `<DB_KIT_PG_DATABASE>` in `register_sources.sql` must be replaced before a real run.
2. **NULL in a domain-checked column** (loyalty_tier, region, order_status, payment_method) is treated as a domain violation and quarantined, per the mapping text "must be in (...) else quarantined". None occur in the profiled data.
3. **Cast failure** = value is not NULL and `TRY_CAST` returns NULL; a NULL source stays NULL and is not quarantined.
4. **`quarantine_rows._source_table`** holds the Bronze table of the rejected row (the mapping said a literal `<various>`).
5. **`fact_orders.items_total`** sums only line items that cast cleanly; an order with an uncastable line gets a total from its good lines (the bad line is quarantined by `fact_order_lines`). Orders with no lines would get NULL and a NULL reconciliation flag.
6. **Load order matters:** `fact_orders` checks `dim_customer`, and `fact_order_lines` checks `fact_orders` and `dim_product`, so run in the order in `config/run_config.yaml`.
7. **OQ1 (a):** `is_amount_reconciled` = `gross − discount = items_total` as written; flag only, rows kept. Expected on the profiled data: 4 of 5 orders flagged false.
8. Bronze `_source_table` and Silver `_source_table` literals include the backticked three-level name.

## DDL checklist (10-point, per table)
All 10 tables: `CREATE TABLE IF NOT EXISTS`, `USING DELTA`, both autoOptimize properties, table + column COMMENTs, parameterized three-level names, NOT NULL keys and metadata, no partitioning (≤7 rows), dimensions before facts. No failures. Items needing a real workspace (syntax of every statement, JDBC reachability) are unverified because nothing was run.

## Not verified
Python notebooks compile (`py_compile`); the SQL has not been parsed by Spark. Run it only after the Stage 6 validation step in a real (non-dry) run.
