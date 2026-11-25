# Migration blueprint — mig-example-project-20261125T062515Z (DRY RUN)

**Source** `postgres:raw_dump` (Azure Database for PostgreSQL, env `DB_KIT_PG_*`) → **landing** `retail_demo.landing` → **Bronze** `retail_demo.bronze` → **Silver** `retail_demo.silver`. Target `databricks`. Dry run: code is generated, nothing is executed, no Databricks access used. Evidence: `artifacts/discovery/.../discovery-report.md`, `assessment.md`, `risks.md`, `source-to-target-mapping.yaml`.

> **Placeholders:** JDBC secret scope `db-kit-demo`, keys `jdbc-user` / `jdbc-password` are placeholders — replace before any real run. Postgres host/database are not recorded; generated code references them as run-time parameters.

## Landing (landing-load)
Per table: register `retail_demo.landing._jdbc_src_<t>` (`USING JDBC`, `jdbc:postgresql://…?sslmode=require`, credentials only via `secret()`), then `CREATE OR REPLACE TABLE retail_demo.landing.raw_<t> AS SELECT <explicit cols>, current_timestamp() AS _landed_at`. Order: customers, products, orders, order_items. Full reload each run. Types: text→STRING, timestamptz→TIMESTAMP (UTC-normalized).

## Bronze (append-only, as-is)
`customers, products, orders, order_items` — all landing columns unchanged (STRING + `_landed_at`) plus `_ingested_at`, `_source_table`. No business logic, no casts. Idempotent: insert only (key, `_landed_at`) pairs not already present. Key: (business key, `_landed_at`).

## Silver (cleaned, typed, rules applied)
| Table | Grain / key | Changes from Bronze (rule) |
|---|---|---|
| dim_customer | customer_id | `full_name`→`customer_name` trimmed; email lower/trim, NULL kept + `is_email_missing` flag (rule-email-nullable-flagged); `signup_date`→DATE; tier/region domain checks (rule-loyalty-tier-domain, rule-region-domain) |
| dim_product | sku | `unit_cost`,`list_price`→DECIMAL(18,2); `is_active`→BOOLEAN |
| fact_orders | order_id | `order_timestamp`→TIMESTAMP_NTZ; amounts→DECIMAL(18,2); status/payment domain checks; derived `items_total`, `is_amount_reconciled`; FK customer_id (rule-referential-integrity) |
| fact_order_lines | item_id | `quantity`→INT, `unit_sold_price`→DECIMAL(18,2); derived `line_amount`; FKs order_id, sku |
| quarantine_rows | source_table, record_key, reason, _run_id | rows failing a cast, domain, or FK check (never silently dropped) |

Load: MERGE on business key from the latest Bronze row per key (`ROW_NUMBER() … ORDER BY _landed_at DESC`), dimensions → fact_orders → fact_order_lines. Delta, `optimizeWrite`+`autoCompact`, no partitioning (≤7 rows; far under 1 GB). All tables carry `_ingested_at`, `_source_table`. Silver business rules are cited per column in the mapping (`business_rule`).

## Quality and reconciliation (for the Validation Agent when run for real)
Row counts source = landing = Bronze (distinct keys); Silver + quarantine = Bronze latest-per-key; PK uniqueness/non-null; domain rules; FK orphan = 0; null-email count = flagged count; reconciliation rule per OQ1. Not run in this dry run.

## Mapping validation result
**0 ERROR, 2 WARNING, 1 INFO.** WARNING: null/blank + dedup handling stated (keys NOT NULL in source; latest `_landed_at` wins); WARNING: `fact_orders.is_amount_reconciled` unresolved (OQ1). INFO: 37 direct, 17 transformed, 4 derived, 23 no_mapping; 1 unresolved. Checked in code: completeness, duplicate columns, source-column existence vs `describe_table`, key non-nullability, FK targets in scope.

## Assessment risks (full list in `risks.md`)
- **OQ1 (High) — needs your decision.** Graph rule: `gross − discount = Σ qty × unit_sold_price`. Data: holds for 1/5 orders (and only because that discount is 0); for 3 more, item total = `gross`; ORD-5005 matches neither. Options: (a) keep the rule as written and flag mismatches (current default; 4 of 5 flagged), (b) reinterpret as `gross = Σ items` (1 flagged: ORD-5005), (c) flag nothing until the owner clarifies. Default (a) is a flag only, nothing is dropped.
- OQ2 no legacy code exists; OQ3 no time zone (TIMESTAMP_NTZ); OQ4 domain violators are quarantined (none today); OQ5 Bronze `_landed_at` = landing load time; R6 JDBC reachability untested; R8 casts in Silver, not Bronze (per `layer-conventions.md`).

## Checkpoints
After landing (counts vs source), after Bronze, after Silver; each step recorded in the run record. In a dry run, generation stops after `docs/`.

## Approval requested
Approve generating `landing/`, `bronze/`, `silver/`, `config/`, `docs/` under `artifacts/generated-code/example-project/mig-example-project-20261125T062515Z/` from this mapping, with the OQ1 handling (a, b or c) you choose. Nothing is executed.
