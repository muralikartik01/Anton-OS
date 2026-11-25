# Transformation: silver.fact_orders

## 1. Overview
- Notebook: `silver/fact_orders.py` (`artifacts/generated-code/example-project/mig-example-project-20261125T062515Z/silver/fact_orders.py`)
- Layer: Silver
- Target: `{silver_catalog}.{silver_schema}.fact_orders`
- Purpose (header cell): Silver order fact from latest Bronze order per order_id, with line-item total and reconciliation flag

## 2. Source tables
- `{bronze}.order_items` (read in the write statement)
- `{bronze}.orders` (read in the write statement)
- `{silver}.dim_customer` (read in the write statement)

## 3. Target load config
- Strategy: upsert (MERGE)
- Key columns: `order_id`
- Quarantine table: `{silver}.quarantine_rows` (insert statement in this notebook)
- Statements executed in order: ddl, quarantine, write

## 4. Filters
```sql
WHERE order_id IS NOT NULL
```
```sql
WHERE item_id IS NOT NULL
```
```sql
WHERE x.reason IS NULL
```

## 5. Join logic
- `LEFT JOIN` ... ON `i.order_id = o.order_id` (alias `i`)

## 6. Transformation logic
### Direct
- `order_id` = `x.order_id`
- `customer_id` = `x.customer_id`
- `store_id` = `x.store_id`
- `items_total` = `x.items_total`
### Cast
- `order_timestamp` = `TRY_CAST(x.order_timestamp AS TIMESTAMP_NTZ)`
- `order_status` = `TRIM(x.order_status)`
- `payment_method` = `TRIM(x.payment_method)`
- `gross_amount` = `TRY_CAST(x.gross_amount AS DECIMAL(18,2))`
- `discount_amount` = `TRY_CAST(x.discount_amount AS DECIMAL(18,2))`
### Derived business rule
- `is_amount_reconciled` = `CASE WHEN x.items_total IS NULL OR TRY_CAST(x.gross_amount AS DECIMAL(18,2)) IS NULL OR TRY_CAST(x.discount_amount AS DECIMAL(18,2)) IS NULL THEN NULL ELSE (TRY_CAST(x.gross_amount AS DECIMAL(18,2)) - TRY_CAST(x.discount_amount AS DECIMAL(18,2)) = x.items_total) END`
### Hardcoded default
N/A
### Ingestion metadata
- `_ingested_at` = `current_timestamp()`
- `_source_table` = `'{bronze}.orders'`

---
Mapping rows: silver.fact_orders.* (incl. rule-order-status-domain, rule-payment-method-domain, rule-referential-integrity, rule-order-amount-reconciles; OQ1 option a) — columns: silver.fact_orders.order_id, silver.fact_orders.customer_id, silver.fact_orders.store_id, silver.fact_orders.items_total, silver.fact_orders.order_timestamp, silver.fact_orders.order_status, silver.fact_orders.payment_method, silver.fact_orders.gross_amount, silver.fact_orders.discount_amount, silver.fact_orders.is_amount_reconciled, silver.fact_orders._ingested_at, silver.fact_orders._source_table
Generated from: `silver/fact_orders.py`
