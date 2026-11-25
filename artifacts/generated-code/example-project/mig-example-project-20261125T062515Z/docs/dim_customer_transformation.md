# Transformation: silver.dim_customer

## 1. Overview
- Notebook: `silver/dim_customer.py` (`artifacts/generated-code/example-project/mig-example-project-20261125T062515Z/silver/dim_customer.py`)
- Layer: Silver
- Target: `{silver_catalog}.{silver_schema}.dim_customer`
- Purpose (header cell): Silver customer dimension from latest Bronze row per customer_id

## 2. Source tables
- `{bronze}.customers` (read in the write statement)

## 3. Target load config
- Strategy: upsert (MERGE)
- Key columns: `customer_id`
- Quarantine table: `{silver}.quarantine_rows` (insert statement in this notebook)
- Statements executed in order: ddl, quarantine, write

## 4. Filters
```sql
WHERE customer_id IS NOT NULL
```
```sql
WHERE x.reason IS NULL
```

## 5. Join logic
N/A

## 6. Transformation logic
### Direct
- `customer_id` = `x.customer_id`
### Cast
- `customer_name` = `TRIM(x.full_name)`
- `email` = `NULLIF(LOWER(TRIM(x.email)), '')`
- `loyalty_tier` = `TRIM(x.loyalty_tier)`
- `signup_date` = `TRY_CAST(x.signup_date AS DATE)`
- `region` = `TRIM(x.region)`
### Derived business rule
- `is_email_missing` = `(x.email IS NULL OR TRIM(x.email) = '')`
### Hardcoded default
N/A
### Ingestion metadata
- `_ingested_at` = `current_timestamp()`
- `_source_table` = `'{bronze}.customers'`

---
Mapping rows: silver.dim_customer.* (17 mapping rows incl. rule-email-nullable-flagged, rule-loyalty-tier-domain, rule-region-domain) — columns: silver.dim_customer.customer_id, silver.dim_customer.customer_name, silver.dim_customer.email, silver.dim_customer.loyalty_tier, silver.dim_customer.signup_date, silver.dim_customer.region, silver.dim_customer.is_email_missing, silver.dim_customer._ingested_at, silver.dim_customer._source_table
Generated from: `silver/dim_customer.py`
