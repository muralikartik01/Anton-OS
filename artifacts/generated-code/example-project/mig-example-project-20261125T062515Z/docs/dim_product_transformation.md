# Transformation: silver.dim_product

## 1. Overview
- Notebook: `silver/dim_product.py` (`artifacts/generated-code/example-project/mig-example-project-20261125T062515Z/silver/dim_product.py`)
- Layer: Silver
- Target: `{silver_catalog}.{silver_schema}.dim_product`
- Purpose (header cell): Silver product dimension from latest Bronze row per sku

## 2. Source tables
- `{bronze}.products` (read in the write statement)

## 3. Target load config
- Strategy: upsert (MERGE)
- Key columns: `sku`
- Quarantine table: `{silver}.quarantine_rows` (insert statement in this notebook)
- Statements executed in order: ddl, quarantine, write

## 4. Filters
```sql
WHERE sku IS NOT NULL
```
```sql
WHERE x.reason IS NULL
```

## 5. Join logic
N/A

## 6. Transformation logic
### Direct
- `sku` = `x.sku`
### Cast
- `product_name` = `TRIM(x.product_name)`
- `category` = `TRIM(x.category)`
- `unit_cost` = `TRY_CAST(x.unit_cost AS DECIMAL(18,2))`
- `list_price` = `TRY_CAST(x.list_price AS DECIMAL(18,2))`
- `is_active` = `TRY_CAST(LOWER(TRIM(x.is_active)) AS BOOLEAN)`
### Derived business rule
N/A
### Hardcoded default
N/A
### Ingestion metadata
- `_ingested_at` = `current_timestamp()`
- `_source_table` = `'{bronze}.products'`

---
Mapping rows: silver.dim_product.* — columns: silver.dim_product.sku, silver.dim_product.product_name, silver.dim_product.category, silver.dim_product.unit_cost, silver.dim_product.list_price, silver.dim_product.is_active, silver.dim_product._ingested_at, silver.dim_product._source_table
Generated from: `silver/dim_product.py`
