# Discovery report — mig-example-project-20261125T062515Z

Source: `postgres:raw_dump` (read via `db-kit-postgres`, read-only). Landing/Bronze/Silver names are placeholders for generated code only (dry run).

## Shortlist (all tables in scope; no `--scope` filter)
| table | confirmed by | graph id | source system (graph) |
|---|---|---|---|
| raw_customers | graph + `list_tables` | ds-customers | CRM |
| raw_products | graph + `list_tables` | ds-products | ERP |
| raw_orders | graph + `list_tables` | ds-orders | POS |
| raw_order_items | graph + `list_tables` | ds-order-items | POS |

No `not_found` entries. Verified: all 4 tables exist in `raw_dump`; schemas from `describe_table` match the graph's `schema` property column-for-column.

## Verified facts (live queries)
- Row counts: customers 5, products 5, orders 5, order_items 7. Every PK is 100% distinct and non-null.
- Every business column is `text` in the source (only `_landed_at` is `timestamptz`). All casts happen downstream.
- FKs declared in source: orders.customer_id→customers; order_items.order_id→orders; order_items.sku→products.
- Cast-failure counts (regex check): 0 for signup_date, order_timestamp, gross/discount_amount, unit_cost/list_price, quantity, unit_sold_price.
- Domain checks: loyalty_tier {Bronze 2, Gold 1, Platinum 1, Silver 1}; region {South 2, North, East, West}; order_status {COMPLETED 4, RETURNED 1}; payment_method {CARD 3, CASH, UPI}; is_active {true 4, false 1}. All within graph rules; CANCELLED never occurs.
- Orphans: 0 for all three FKs. Orders without items: 0. Duplicate emails: 0. Customers with NULL email: 1 of 5.
- Negatives: none in cost/price/quantity. discount > gross: 0.
- `_landed_at` is a single value for all rows (2026-11-24 17:29:29 UTC) — no load-history spread.
- Temporal: signup_date 2023-11-05..2026-02-18; order_timestamp 2026-11-20 10:15:00..2026-11-23 18:20:00 (no zone in the string).

## Anomaly (verified, unexplained)
- **[High]** Rule `rule-order-amount-reconciles` (graph) says `gross_amount - discount_amount = SUM(quantity * unit_sold_price)`. Data: 4 of 5 orders violate it as written. For ORD-5001 (gross 200, disc 20), 5003 (120/10), 5004 (1500/225) the item total equals `gross_amount`, i.e. line prices look pre-discount; ORD-5002 passes only because its discount is 0; ORD-5005 (gross 75, items 65) matches neither reading. Cause unknown → open question OQ1.

## Code inventory
No legacy pipeline/transformation code was found in the repository paths declared in `config/project.yaml`; the repo holds only the framework. **Gap:** no legacy logic exists to migrate, so Silver logic derives solely from graph business rules and profiling. Lineage/scheduling: unknown (not in graph or repo).

## Graph context used
`list_schema` (labels Dataset, BusinessRule, SourceSystem), `query_context` Dataset (4) and BusinessRule (7). `get_lineage` not called (no pipeline nodes exist). No `annotate_entity` writes made (the gaps are recorded in `risks.md`).

## Limits of profiling (stated, not hidden)
Targeted Level 1/4 profiling (counts, nulls, key uniqueness, cast failures, domains, orphans, reconciliation). Level 2 percentiles and the 30-day volume series were not run — 5–7 rows per table make them uninformative. `profile.csv` carries only measured values; unmeasured cells are blank.

## Context budget
4 Dataset nodes, 7 rule nodes, 4 describe calls, 4 SQL queries; no large files read.
