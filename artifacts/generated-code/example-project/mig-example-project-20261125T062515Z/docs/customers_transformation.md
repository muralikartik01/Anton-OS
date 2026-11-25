# Transformation: bronze.customers

## 1. Overview
- Notebook: `bronze/customers.py` (`artifacts/generated-code/example-project/mig-example-project-20261125T062515Z/bronze/customers.py`)
- Layer: Bronze
- Target: `{bronze_catalog}.{bronze_schema}.customers`
- Purpose (header cell): as-is append of landing raw_customers

## 2. Source tables
- `{landing}.raw_customers` (read in the write statement)

## 3. Target load config
- Strategy: append (idempotent: skips (key,_landed_at) already present)
- Key columns: `customer_id,_landed_at`
- Quarantine table: N/A
- Statements executed in order: ddl, write

## 4. Filters
```sql
WHERE l.customer_id IS NOT NULL
```
```sql
AND NOT EXISTS (SELECT 1 FROM {bronze}.customers AS b WHERE b.customer_id = l.customer_id AND b._landed_at = l._landed_at)
```

## 5. Join logic
N/A

## 6. Transformation logic
### Direct
- `customer_id` = `l.customer_id`
- `full_name` = `l.full_name`
- `email` = `l.email`
- `loyalty_tier` = `l.loyalty_tier`
- `signup_date` = `l.signup_date`
- `region` = `l.region`
- `_landed_at` = `l._landed_at`
### Cast
N/A
### Derived business rule
N/A
### Hardcoded default
N/A
### Ingestion metadata
- `_ingested_at` = `current_timestamp()`
- `_source_table` = `'{landing}.raw_customers'`

---
Mapping rows: bronze.customers.* (direct + _ingested_at/_source_table) — columns: bronze.customers.customer_id, bronze.customers.full_name, bronze.customers.email, bronze.customers.loyalty_tier, bronze.customers.signup_date, bronze.customers.region, bronze.customers._landed_at, bronze.customers._ingested_at, bronze.customers._source_table
Generated from: `bronze/customers.py`
