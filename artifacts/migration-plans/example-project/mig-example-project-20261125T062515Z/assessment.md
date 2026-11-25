# Assessment — mig-example-project-20261125T062515Z
Evidence: `artifacts/discovery/example-project/mig-example-project-20261125T062515Z/discovery-report.md`.

| Table | Complexity | Dependencies | Risk | Evidence | Open question |
|---|---|---|---|---|---|
| raw_customers | Low | none (parent) | Low: 1 NULL email (flag, keep); domain checks pass | 5 rows, 7 cols, 1 cast (signup_date), 2 domain rules + email rule | OQ4 (domain violators: quarantine vs flag) |
| raw_products | Low | none (parent) | Low | 5 rows, 3 casts (unit_cost, list_price, is_active), 0 cast failures | none |
| raw_orders | **Medium** | customers | **High**: reconciliation rule contradicts data in 4/5 orders | 5 rows, 4 casts, 2 domain rules, FK + reconciliation rule | OQ1, OQ3 |
| raw_order_items | Medium | orders, products | Low (0 orphans), but feeds OQ1 | 7 rows, 2 casts, 2 FKs | OQ1 |

## Dependency risk
Parents before children: customers, products → orders → order_items. No orphans, no cycles. FKs are declared in the source and verified.

## Ambiguous / undocumented logic
OQ1 reconciliation rule vs data; OQ2 no legacy pipeline code exists (nothing to port, rules come only from graph); OQ3 order_timestamp has no zone; OQ4 domain-violation policy (graph says domains but is silent on handling); OQ5 `_landed_at` semantics (single value in source).

## Volume and incremental
Tiny (5–7 rows per table). The source has no incremental key (single `_landed_at` for all rows), so landing is a full reload each run; Bronze appends only unseen (key, `_landed_at`) pairs; Silver MERGEs on the business key from the latest Bronze row. No partitioning (far under 1 GB).

## Platform compatibility
Source types map cleanly (text→STRING, timestamptz→TIMESTAMP; no unsupported types, per `postgres-to-spark-type-mapping.md`). Landing needs the warehouse to reach the Postgres server over JDBC (network/firewall) — not testable in a dry run. JDBC secret scope/keys are placeholders. No Gold, no production writes.

## Migration order
1. landing (4 tables, parents first) — faithful copy via JDBC
2. bronze customers, products — parents
3. bronze orders, order_items — children
4. silver dim_customer, dim_product — dimensions
5. silver fact_orders, then fact_order_lines — facts after their dimensions/parent
6. silver quarantine_rows — written by the steps above
