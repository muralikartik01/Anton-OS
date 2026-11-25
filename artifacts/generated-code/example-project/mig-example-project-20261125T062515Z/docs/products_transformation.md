# Transformation: bronze.products

## 1. Overview
- Notebook: `bronze/products.py` (`artifacts/generated-code/example-project/mig-example-project-20261125T062515Z/bronze/products.py`)
- Layer: Bronze
- Target: `{bronze_catalog}.{bronze_schema}.products`
- Purpose (header cell): as-is append of landing raw_products

## 2. Source tables
- `{landing}.raw_products` (read in the write statement)

## 3. Target load config
- Strategy: append (idempotent: skips (key,_landed_at) already present)
- Key columns: `sku,_landed_at`
- Quarantine table: N/A
- Statements executed in order: ddl, write

## 4. Filters
```sql
WHERE l.sku IS NOT NULL
```
```sql
AND NOT EXISTS (SELECT 1 FROM {bronze}.products AS b WHERE b.sku = l.sku AND b._landed_at = l._landed_at)
```

## 5. Join logic
N/A

## 6. Transformation logic
### Direct
- `sku` = `l.sku`
- `product_name` = `l.product_name`
- `category` = `l.category`
- `unit_cost` = `l.unit_cost`
- `list_price` = `l.list_price`
- `is_active` = `l.is_active`
- `_landed_at` = `l._landed_at`
### Cast
N/A
### Derived business rule
N/A
### Hardcoded default
N/A
### Ingestion metadata
- `_ingested_at` = `current_timestamp()`
- `_source_table` = `'{landing}.raw_products'`

---
Mapping rows: bronze.products.* (direct + _ingested_at/_source_table) — columns: bronze.products.sku, bronze.products.product_name, bronze.products.category, bronze.products.unit_cost, bronze.products.list_price, bronze.products.is_active, bronze.products._landed_at, bronze.products._ingested_at, bronze.products._source_table
Generated from: `bronze/products.py`
