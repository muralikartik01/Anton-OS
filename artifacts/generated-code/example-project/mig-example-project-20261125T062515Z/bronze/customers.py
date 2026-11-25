# Databricks notebook source
# MAGIC %md
# MAGIC # bronze.customers
# MAGIC - Purpose: as-is append of landing raw_customers
# MAGIC - Source: `{landing}.raw_customers`
# MAGIC - Target: `{bronze_catalog}.{bronze_schema}.customers`
# MAGIC - Load strategy: append (idempotent: skips (key,_landed_at) already present); keys: customer_id,_landed_at
# MAGIC - Mapping rows: bronze.customers.* (direct + _ingested_at/_source_table)
# MAGIC - Run: mig-example-project-20261125T062515Z (approved blueprint, dry-run generation; never executed by this agent)


# COMMAND ----------

dbutils.widgets.text("landing_catalog", "")
dbutils.widgets.text("landing_schema", "")
dbutils.widgets.text("bronze_catalog", "")
dbutils.widgets.text("bronze_schema", "")
dbutils.widgets.text("run_id", "")
dbutils.widgets.text("project_id", "")

landing_catalog = dbutils.widgets.get("landing_catalog")
landing_schema = dbutils.widgets.get("landing_schema")
bronze_catalog = dbutils.widgets.get("bronze_catalog")
bronze_schema = dbutils.widgets.get("bronze_schema")
run_id = dbutils.widgets.get("run_id")
project_id = dbutils.widgets.get("project_id")

# COMMAND ----------

landing = f"`{landing_catalog}`.`{landing_schema}`"
bronze = f"`{bronze_catalog}`.`{bronze_schema}`"
LOAD_STRATEGY = "append"
MERGE_KEYS = ['customer_id', '_landed_at']
rows_written = 0

# COMMAND ----------

# ddl
STMT_DDL = f"""
CREATE TABLE IF NOT EXISTS {bronze}.customers (
    customer_id STRING NOT NULL COMMENT 'Source column customer_id from raw_dump.raw_customers, kept as-is',
    full_name STRING COMMENT 'Source column full_name from raw_dump.raw_customers, kept as-is',
    email STRING COMMENT 'Source column email from raw_dump.raw_customers, kept as-is',
    loyalty_tier STRING COMMENT 'Source column loyalty_tier from raw_dump.raw_customers, kept as-is',
    signup_date STRING COMMENT 'Source column signup_date from raw_dump.raw_customers, kept as-is',
    region STRING COMMENT 'Source column region from raw_dump.raw_customers, kept as-is',
    _landed_at TIMESTAMP NOT NULL COMMENT 'Landing load time of the row',
    _ingested_at TIMESTAMP NOT NULL COMMENT 'Load timestamp of the run that wrote this row',
    _source_table STRING NOT NULL COMMENT 'Fully qualified landing table of this row'
)
USING DELTA
COMMENT 'Bronze CRM customers: as-is copy of landing raw_customers, append-only'
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact'   = 'true'
)
"""
spark.sql(STMT_DDL)

# COMMAND ----------

# write
STMT_WRITE = f"""
INSERT INTO {bronze}.customers (customer_id, full_name, email, loyalty_tier, signup_date, region, _landed_at, _ingested_at, _source_table)
SELECT l.customer_id, l.full_name, l.email, l.loyalty_tier, l.signup_date, l.region, l._landed_at, current_timestamp(), '{landing}.raw_customers'
FROM {landing}.raw_customers AS l
WHERE l.customer_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM {bronze}.customers AS b WHERE b.customer_id = l.customer_id AND b._landed_at = l._landed_at)
"""
spark.sql(STMT_WRITE)

# COMMAND ----------

# Row-count report
print("bronze.customers rows:", spark.sql(f"SELECT COUNT(*) AS n FROM {bronze}.customers").collect()[0]["n"])
