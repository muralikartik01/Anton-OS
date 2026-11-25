# Databricks notebook source
# MAGIC %md
# MAGIC # bronze.orders
# MAGIC - Purpose: as-is append of landing raw_orders
# MAGIC - Source: `{landing}.raw_orders`
# MAGIC - Target: `{bronze_catalog}.{bronze_schema}.orders`
# MAGIC - Load strategy: append (idempotent: skips (key,_landed_at) already present); keys: order_id,_landed_at
# MAGIC - Mapping rows: bronze.orders.* (direct + _ingested_at/_source_table)
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
MERGE_KEYS = ['order_id', '_landed_at']
rows_written = 0

# COMMAND ----------

# ddl
STMT_DDL = f"""
CREATE TABLE IF NOT EXISTS {bronze}.orders (
    order_id STRING NOT NULL COMMENT 'Source column order_id from raw_dump.raw_orders, kept as-is',
    customer_id STRING NOT NULL COMMENT 'Source column customer_id from raw_dump.raw_orders, kept as-is',
    store_id STRING COMMENT 'Source column store_id from raw_dump.raw_orders, kept as-is',
    order_timestamp STRING COMMENT 'Source column order_timestamp from raw_dump.raw_orders, kept as-is',
    order_status STRING COMMENT 'Source column order_status from raw_dump.raw_orders, kept as-is',
    payment_method STRING COMMENT 'Source column payment_method from raw_dump.raw_orders, kept as-is',
    gross_amount STRING COMMENT 'Source column gross_amount from raw_dump.raw_orders, kept as-is',
    discount_amount STRING COMMENT 'Source column discount_amount from raw_dump.raw_orders, kept as-is',
    _landed_at TIMESTAMP NOT NULL COMMENT 'Landing load time of the row',
    _ingested_at TIMESTAMP NOT NULL COMMENT 'Load timestamp of the run that wrote this row',
    _source_table STRING NOT NULL COMMENT 'Fully qualified landing table of this row'
)
USING DELTA
COMMENT 'Bronze POS orders: as-is copy of landing raw_orders, append-only'
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact'   = 'true'
)
"""
spark.sql(STMT_DDL)

# COMMAND ----------

# write
STMT_WRITE = f"""
INSERT INTO {bronze}.orders (order_id, customer_id, store_id, order_timestamp, order_status, payment_method, gross_amount, discount_amount, _landed_at, _ingested_at, _source_table)
SELECT l.order_id, l.customer_id, l.store_id, l.order_timestamp, l.order_status, l.payment_method, l.gross_amount, l.discount_amount, l._landed_at, current_timestamp(), '{landing}.raw_orders'
FROM {landing}.raw_orders AS l
WHERE l.order_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM {bronze}.orders AS b WHERE b.order_id = l.order_id AND b._landed_at = l._landed_at)
"""
spark.sql(STMT_WRITE)

# COMMAND ----------

# Row-count report
print("bronze.orders rows:", spark.sql(f"SELECT COUNT(*) AS n FROM {bronze}.orders").collect()[0]["n"])
