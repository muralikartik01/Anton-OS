# Transformation: bronze.orders

## 1. Overview
- Notebook: `bronze/orders.py` (`artifacts/generated-code/example-project/mig-example-project-20261125T062515Z/bronze/orders.py`)
- Layer: Bronze
- Target: `{bronze_catalog}.{bronze_schema}.orders`
- Purpose (header cell): as-is append of landing raw_orders

## 2. Source tables
- `{landing}.raw_orders` (read in the write statement)

## 3. Target load config
- Strategy: append (idempotent: skips (key,_landed_at) already present)
- Key columns: `order_id,_landed_at`
- Quarantine table: N/A
- Statements executed in order: ddl, write

## 4. Filters
```sql
WHERE l.order_id IS NOT NULL
```
```sql
AND NOT EXISTS (SELECT 1 FROM {bronze}.orders AS b WHERE b.order_id = l.order_id AND b._landed_at = l._landed_at)
```

## 5. Join logic
N/A

## 6. Transformation logic
### Direct
- `order_id` = `l.order_id`
- `customer_id` = `l.customer_id`
- `store_id` = `l.store_id`
- `order_timestamp` = `l.order_timestamp`
- `order_status` = `l.order_status`
- `payment_method` = `l.payment_method`
- `gross_amount` = `l.gross_amount`
- `discount_amount` = `l.discount_amount`
- `_landed_at` = `l._landed_at`
### Cast
N/A
### Derived business rule
N/A
### Hardcoded default
N/A
### Ingestion metadata
- `_ingested_at` = `current_timestamp()`
- `_source_table` = `'{landing}.raw_orders'`

---
Mapping rows: bronze.orders.* (direct + _ingested_at/_source_table) — columns: bronze.orders.order_id, bronze.orders.customer_id, bronze.orders.store_id, bronze.orders.order_timestamp, bronze.orders.order_status, bronze.orders.payment_method, bronze.orders.gross_amount, bronze.orders.discount_amount, bronze.orders._landed_at, bronze.orders._ingested_at, bronze.orders._source_table
Generated from: `bronze/orders.py`
