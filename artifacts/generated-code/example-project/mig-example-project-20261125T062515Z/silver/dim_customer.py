# Databricks notebook source
# MAGIC %md
# MAGIC # silver.dim_customer
# MAGIC - Purpose: Silver customer dimension from latest Bronze row per customer_id
# MAGIC - Source: `{bronze}.customers`
# MAGIC - Target: `{silver_catalog}.{silver_schema}.dim_customer`
# MAGIC - Load strategy: upsert (MERGE); keys: customer_id
# MAGIC - Mapping rows: silver.dim_customer.* (17 mapping rows incl. rule-email-nullable-flagged, rule-loyalty-tier-domain, rule-region-domain)
# MAGIC - Run: mig-example-project-20261125T062515Z (approved blueprint, dry-run generation; never executed by this agent)


# COMMAND ----------

dbutils.widgets.text("bronze_catalog", "")
dbutils.widgets.text("bronze_schema", "")
dbutils.widgets.text("silver_catalog", "")
dbutils.widgets.text("silver_schema", "")
dbutils.widgets.text("run_id", "")
dbutils.widgets.text("project_id", "")

bronze_catalog = dbutils.widgets.get("bronze_catalog")
bronze_schema = dbutils.widgets.get("bronze_schema")
silver_catalog = dbutils.widgets.get("silver_catalog")
silver_schema = dbutils.widgets.get("silver_schema")
run_id = dbutils.widgets.get("run_id")
project_id = dbutils.widgets.get("project_id")

# COMMAND ----------

bronze = f"`{bronze_catalog}`.`{bronze_schema}`"
silver = f"`{silver_catalog}`.`{silver_schema}`"
LOAD_STRATEGY = "upsert"
MERGE_KEYS = ['customer_id']
rows_written = 0

# COMMAND ----------

# ddl
STMT_DDL = f"""
CREATE TABLE IF NOT EXISTS {silver}.dim_customer (
    customer_id STRING NOT NULL COMMENT 'Business key from the CRM customer table',
    customer_name STRING COMMENT 'Customer display name, trimmed (source full_name)',
    email STRING COMMENT 'Lower-cased trimmed email; NULL kept',
    is_email_missing BOOLEAN NOT NULL COMMENT 'True when the source email is NULL or blank (rule-email-nullable-flagged)',
    loyalty_tier STRING COMMENT 'Loyalty tier: Bronze, Silver, Gold or Platinum',
    signup_date DATE COMMENT 'Signup date cast from source string',
    region STRING COMMENT 'Region: North, South, East or West',
    _ingested_at TIMESTAMP NOT NULL COMMENT 'Load timestamp of the run that wrote this row',
    _source_table STRING NOT NULL COMMENT 'Fully qualified Bronze table of this row'
)
USING DELTA
COMMENT 'Silver customer dimension, one row per customer_id'
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact'   = 'true'
)
"""
spark.sql(STMT_DDL)

# COMMAND ----------

# quarantine
STMT_QUARANTINE = f"""
INSERT INTO {silver}.quarantine_rows (source_table, record_key, reason, row_json, _run_id, _ingested_at, _source_table)
SELECT '{bronze}.customers', x.customer_id, x.reason, TO_JSON(STRUCT(x.customer_id, x.full_name, x.email, x.loyalty_tier, x.signup_date, x.region)), '{run_id}', current_timestamp(), '{bronze}.customers'
FROM (
    SELECT customer_id, full_name, email, loyalty_tier, signup_date, region, CASE
      WHEN signup_date IS NOT NULL AND TRY_CAST(signup_date AS DATE) IS NULL THEN 'cast_failure:signup_date'
      WHEN NOT COALESCE(TRIM(loyalty_tier) IN ('Bronze', 'Silver', 'Gold', 'Platinum'), FALSE) THEN 'domain_violation:rule-loyalty-tier-domain'
      WHEN NOT COALESCE(TRIM(region) IN ('North', 'South', 'East', 'West'), FALSE) THEN 'domain_violation:rule-region-domain'
      ELSE NULL END AS reason
    FROM (
      SELECT customer_id, full_name, email, loyalty_tier, signup_date, region FROM (
    SELECT customer_id, full_name, email, loyalty_tier, signup_date, region, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY _landed_at DESC) AS rn
    FROM {bronze}.customers
    WHERE customer_id IS NOT NULL
  ) WHERE rn = 1
    )
) AS x
WHERE x.reason IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM {silver}.quarantine_rows AS q WHERE q.source_table = '{bronze}.customers' AND q.record_key = x.customer_id AND q.reason = x.reason AND q._run_id = '{run_id}')
"""
spark.sql(STMT_QUARANTINE)

# COMMAND ----------

# write
STMT_WRITE = f"""
MERGE INTO {silver}.dim_customer AS t
USING (
  SELECT
    x.customer_id AS customer_id,
    TRIM(x.full_name) AS customer_name,
    NULLIF(LOWER(TRIM(x.email)), '') AS email,
    (x.email IS NULL OR TRIM(x.email) = '') AS is_email_missing,
    TRIM(x.loyalty_tier) AS loyalty_tier,
    TRY_CAST(x.signup_date AS DATE) AS signup_date,
    TRIM(x.region) AS region,
    current_timestamp() AS _ingested_at,
    '{bronze}.customers' AS _source_table
  FROM (
    SELECT customer_id, full_name, email, loyalty_tier, signup_date, region, CASE
      WHEN signup_date IS NOT NULL AND TRY_CAST(signup_date AS DATE) IS NULL THEN 'cast_failure:signup_date'
      WHEN NOT COALESCE(TRIM(loyalty_tier) IN ('Bronze', 'Silver', 'Gold', 'Platinum'), FALSE) THEN 'domain_violation:rule-loyalty-tier-domain'
      WHEN NOT COALESCE(TRIM(region) IN ('North', 'South', 'East', 'West'), FALSE) THEN 'domain_violation:rule-region-domain'
      ELSE NULL END AS reason
    FROM (
      SELECT customer_id, full_name, email, loyalty_tier, signup_date, region FROM (
    SELECT customer_id, full_name, email, loyalty_tier, signup_date, region, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY _landed_at DESC) AS rn
    FROM {bronze}.customers
    WHERE customer_id IS NOT NULL
  ) WHERE rn = 1
    )
  ) AS x
  WHERE x.reason IS NULL
) AS s
ON t.customer_id = s.customer_id
WHEN MATCHED THEN UPDATE SET
    t.customer_name = s.customer_name,
    t.email = s.email,
    t.is_email_missing = s.is_email_missing,
    t.loyalty_tier = s.loyalty_tier,
    t.signup_date = s.signup_date,
    t.region = s.region,
    t._ingested_at = s._ingested_at,
    t._source_table = s._source_table
WHEN NOT MATCHED THEN INSERT (customer_id, customer_name, email, is_email_missing, loyalty_tier, signup_date, region, _ingested_at, _source_table)
VALUES (s.customer_id, s.customer_name, s.email, s.is_email_missing, s.loyalty_tier, s.signup_date, s.region, s._ingested_at, s._source_table)
"""
spark.sql(STMT_WRITE)

# COMMAND ----------

# Row-count report
print("silver.dim_customer rows:", spark.sql(f"SELECT COUNT(*) AS n FROM {silver}.dim_customer").collect()[0]["n"])
