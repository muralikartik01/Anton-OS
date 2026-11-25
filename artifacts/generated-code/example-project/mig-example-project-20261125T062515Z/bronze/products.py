# Databricks notebook source
# MAGIC %md
# MAGIC # bronze.products
# MAGIC - Purpose: as-is append of landing raw_products
# MAGIC - Source: `{landing}.raw_products`
# MAGIC - Target: `{bronze_catalog}.{bronze_schema}.products`
# MAGIC - Load strategy: append (idempotent: skips (key,_landed_at) already present); keys: sku,_landed_at
# MAGIC - Mapping rows: bronze.products.* (direct + _ingested_at/_source_table)
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
MERGE_KEYS = ['sku', '_landed_at']
rows_written = 0

# COMMAND ----------

# ddl
STMT_DDL = f"""
CREATE TABLE IF NOT EXISTS {bronze}.products (
    sku STRING NOT NULL COMMENT 'Source column sku from raw_dump.raw_products, kept as-is',
    product_name STRING COMMENT 'Source column product_name from raw_dump.raw_products, kept as-is',
    category STRING COMMENT 'Source column category from raw_dump.raw_products, kept as-is',
    unit_cost STRING COMMENT 'Source column unit_cost from raw_dump.raw_products, kept as-is',
    list_price STRING COMMENT 'Source column list_price from raw_dump.raw_products, kept as-is',
    is_active STRING COMMENT 'Source column is_active from raw_dump.raw_products, kept as-is',
    _landed_at TIMESTAMP NOT NULL COMMENT 'Landing load time of the row',
    _ingested_at TIMESTAMP NOT NULL COMMENT 'Load timestamp of the run that wrote this row',
    _source_table STRING NOT NULL COMMENT 'Fully qualified landing table of this row'
)
USING DELTA
COMMENT 'Bronze ERP products: as-is copy of landing raw_products, append-only'
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact'   = 'true'
)
"""
spark.sql(STMT_DDL)

# COMMAND ----------

# write
STMT_WRITE = f"""
INSERT INTO {bronze}.products (sku, product_name, category, unit_cost, list_price, is_active, _landed_at, _ingested_at, _source_table)
SELECT l.sku, l.product_name, l.category, l.unit_cost, l.list_price, l.is_active, l._landed_at, current_timestamp(), '{landing}.raw_products'
FROM {landing}.raw_products AS l
WHERE l.sku IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM {bronze}.products AS b WHERE b.sku = l.sku AND b._landed_at = l._landed_at)
"""
spark.sql(STMT_WRITE)

# COMMAND ----------

# Row-count report
print("bronze.products rows:", spark.sql(f"SELECT COUNT(*) AS n FROM {bronze}.products").collect()[0]["n"])
