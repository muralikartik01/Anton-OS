# Databricks notebook source
# MAGIC %md
# MAGIC # bronze.order_items
# MAGIC - Purpose: as-is append of landing raw_order_items
# MAGIC - Source: `{landing}.raw_order_items`
# MAGIC - Target: `{bronze_catalog}.{bronze_schema}.order_items`
# MAGIC - Load strategy: append (idempotent: skips (key,_landed_at) already present); keys: item_id,_landed_at
# MAGIC - Mapping rows: bronze.order_items.* (direct + _ingested_at/_source_table)
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
MERGE_KEYS = ['item_id', '_landed_at']
rows_written = 0

# COMMAND ----------

# ddl
STMT_DDL = f"""
CREATE TABLE IF NOT EXISTS {bronze}.order_items (
    item_id STRING NOT NULL COMMENT 'Source column item_id from raw_dump.raw_order_items, kept as-is',
    order_id STRING NOT NULL COMMENT 'Source column order_id from raw_dump.raw_order_items, kept as-is',
    sku STRING NOT NULL COMMENT 'Source column sku from raw_dump.raw_order_items, kept as-is',
    quantity STRING COMMENT 'Source column quantity from raw_dump.raw_order_items, kept as-is',
    unit_sold_price STRING COMMENT 'Source column unit_sold_price from raw_dump.raw_order_items, kept as-is',
    _landed_at TIMESTAMP NOT NULL COMMENT 'Landing load time of the row',
    _ingested_at TIMESTAMP NOT NULL COMMENT 'Load timestamp of the run that wrote this row',
    _source_table STRING NOT NULL COMMENT 'Fully qualified landing table of this row'
)
USING DELTA
COMMENT 'Bronze POS order items: as-is copy of landing raw_order_items, append-only'
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact'   = 'true'
)
"""
spark.sql(STMT_DDL)

# COMMAND ----------

# write
STMT_WRITE = f"""
INSERT INTO {bronze}.order_items (item_id, order_id, sku, quantity, unit_sold_price, _landed_at, _ingested_at, _source_table)
SELECT l.item_id, l.order_id, l.sku, l.quantity, l.unit_sold_price, l._landed_at, current_timestamp(), '{landing}.raw_order_items'
FROM {landing}.raw_order_items AS l
WHERE l.item_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM {bronze}.order_items AS b WHERE b.item_id = l.item_id AND b._landed_at = l._landed_at)
"""
spark.sql(STMT_WRITE)

# COMMAND ----------

# Row-count report
print("bronze.order_items rows:", spark.sql(f"SELECT COUNT(*) AS n FROM {bronze}.order_items").collect()[0]["n"])
