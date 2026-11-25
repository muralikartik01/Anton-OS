# Transformation: bronze.order_items

## 1. Overview
- Notebook: `bronze/order_items.py` (`artifacts/generated-code/example-project/mig-example-project-20261125T062515Z/bronze/order_items.py`)
- Layer: Bronze
- Target: `{bronze_catalog}.{bronze_schema}.order_items`
- Purpose (header cell): as-is append of landing raw_order_items

## 2. Source tables
- `{landing}.raw_order_items` (read in the write statement)

## 3. Target load config
- Strategy: append (idempotent: skips (key,_landed_at) already present)
- Key columns: `item_id,_landed_at`
- Quarantine table: N/A
- Statements executed in order: ddl, write

## 4. Filters
```sql
WHERE l.item_id IS NOT NULL
```
```sql
AND NOT EXISTS (SELECT 1 FROM {bronze}.order_items AS b WHERE b.item_id = l.item_id AND b._landed_at = l._landed_at)
```

## 5. Join logic
N/A

## 6. Transformation logic
### Direct
- `item_id` = `l.item_id`
- `order_id` = `l.order_id`
- `sku` = `l.sku`
- `quantity` = `l.quantity`
- `unit_sold_price` = `l.unit_sold_price`
- `_landed_at` = `l._landed_at`
### Cast
N/A
### Derived business rule
N/A
### Hardcoded default
N/A
### Ingestion metadata
- `_ingested_at` = `current_timestamp()`
- `_source_table` = `'{landing}.raw_order_items'`

---
Mapping rows: bronze.order_items.* (direct + _ingested_at/_source_table) — columns: bronze.order_items.item_id, bronze.order_items.order_id, bronze.order_items.sku, bronze.order_items.quantity, bronze.order_items.unit_sold_price, bronze.order_items._landed_at, bronze.order_items._ingested_at, bronze.order_items._source_table
Generated from: `bronze/order_items.py`
