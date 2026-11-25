# Transformation: silver.fact_order_lines

## 1. Overview
- Notebook: `silver/fact_order_lines.py` (`artifacts/generated-code/example-project/mig-example-project-20261125T062515Z/silver/fact_order_lines.py`)
- Layer: Silver
- Target: `{silver_catalog}.{silver_schema}.fact_order_lines`
- Purpose (header cell): Silver order-line fact from latest Bronze row per item_id

## 2. Source tables
- `{bronze}.order_items` (read in the write statement)
- `{silver}.dim_product` (read in the write statement)
- `{silver}.fact_orders` (read in the write statement)

## 3. Target load config
- Strategy: upsert (MERGE)
- Key columns: `item_id`
- Quarantine table: `{silver}.quarantine_rows` (insert statement in this notebook)
- Statements executed in order: ddl, quarantine, write

## 4. Filters
```sql
WHERE item_id IS NOT NULL
```
```sql
WHERE x.reason IS NULL
```

## 5. Join logic
N/A

## 6. Transformation logic
### Direct
- `item_id` = `x.item_id`
- `order_id` = `x.order_id`
- `sku` = `x.sku`
### Cast
- `quantity` = `TRY_CAST(x.quantity AS INT)`
- `unit_sold_price` = `TRY_CAST(x.unit_sold_price AS DECIMAL(18,2))`
### Derived business rule
- `line_amount` = `TRY_CAST(x.quantity AS INT) * TRY_CAST(x.unit_sold_price AS DECIMAL(18,2))`
### Hardcoded default
N/A
### Ingestion metadata
- `_ingested_at` = `current_timestamp()`
- `_source_table` = `'{bronze}.order_items'`

---
Mapping rows: silver.fact_order_lines.* (incl. rule-referential-integrity) — columns: silver.fact_order_lines.item_id, silver.fact_order_lines.order_id, silver.fact_order_lines.sku, silver.fact_order_lines.quantity, silver.fact_order_lines.unit_sold_price, silver.fact_order_lines.line_amount, silver.fact_order_lines._ingested_at, silver.fact_order_lines._source_table
Generated from: `silver/fact_order_lines.py`
