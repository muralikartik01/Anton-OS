# Databricks notebook source
# MAGIC %md
# MAGIC # silver.fact_order_lines
# MAGIC - Purpose: Silver order-line fact from latest Bronze row per item_id
# MAGIC - Source: `{bronze}.order_items`, `{silver}.fact_orders`, `{silver}.dim_product`
# MAGIC - Target: `{silver_catalog}.{silver_schema}.fact_order_lines`
# MAGIC - Load strategy: upsert (MERGE); keys: item_id
# MAGIC - Mapping rows: silver.fact_order_lines.* (incl. rule-referential-integrity)
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
MERGE_KEYS = ['item_id']
rows_written = 0

# COMMAND ----------

# ddl
STMT_DDL = f"""
CREATE TABLE IF NOT EXISTS {silver}.fact_order_lines (
    item_id STRING NOT NULL COMMENT 'Business key from the POS order item table',
    order_id STRING NOT NULL COMMENT 'Order of the line; FK to fact_orders',
    sku STRING NOT NULL COMMENT 'Product of the line; FK to dim_product',
    quantity INT COMMENT 'Quantity cast from source string',
    unit_sold_price DECIMAL(18,2) COMMENT 'Unit sold price cast from source string',
    line_amount DECIMAL(18,2) COMMENT 'quantity times unit_sold_price',
    _ingested_at TIMESTAMP NOT NULL COMMENT 'Load timestamp of the run that wrote this row',
    _source_table STRING NOT NULL COMMENT 'Fully qualified Bronze table of this row'
)
USING DELTA
COMMENT 'Silver order-line fact, one row per item_id'
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
SELECT '{bronze}.order_items', x.item_id, x.reason, TO_JSON(STRUCT(x.item_id, x.order_id, x.sku, x.quantity, x.unit_sold_price)), '{run_id}', current_timestamp(), '{bronze}.order_items'
FROM (
    SELECT li.item_id, li.order_id, li.sku, li.quantity, li.unit_sold_price, CASE
      WHEN quantity IS NOT NULL AND TRY_CAST(quantity AS INT) IS NULL THEN 'cast_failure:quantity'
      WHEN unit_sold_price IS NOT NULL AND TRY_CAST(unit_sold_price AS DECIMAL(18,2)) IS NULL THEN 'cast_failure:unit_sold_price'
      WHEN NOT EXISTS (SELECT 1 FROM {silver}.fact_orders AS fo WHERE fo.order_id = li.order_id) THEN 'orphan_fk:order_id'
      WHEN NOT EXISTS (SELECT 1 FROM {silver}.dim_product AS dp WHERE dp.sku = li.sku) THEN 'orphan_fk:sku'
      ELSE NULL END AS reason
    FROM (
      SELECT item_id, order_id, sku, quantity, unit_sold_price FROM (
    SELECT item_id, order_id, sku, quantity, unit_sold_price, ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY _landed_at DESC) AS rn
    FROM {bronze}.order_items
    WHERE item_id IS NOT NULL
  ) WHERE rn = 1
    ) AS li
) AS x
WHERE x.reason IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM {silver}.quarantine_rows AS q WHERE q.source_table = '{bronze}.order_items' AND q.record_key = x.item_id AND q.reason = x.reason AND q._run_id = '{run_id}')
"""
spark.sql(STMT_QUARANTINE)

# COMMAND ----------

# write
STMT_WRITE = f"""
MERGE INTO {silver}.fact_order_lines AS t
USING (
  SELECT
    x.item_id AS item_id,
    x.order_id AS order_id,
    x.sku AS sku,
    TRY_CAST(x.quantity AS INT) AS quantity,
    TRY_CAST(x.unit_sold_price AS DECIMAL(18,2)) AS unit_sold_price,
    TRY_CAST(x.quantity AS INT) * TRY_CAST(x.unit_sold_price AS DECIMAL(18,2)) AS line_amount,
    current_timestamp() AS _ingested_at,
    '{bronze}.order_items' AS _source_table
  FROM (
    SELECT li.item_id, li.order_id, li.sku, li.quantity, li.unit_sold_price, CASE
      WHEN quantity IS NOT NULL AND TRY_CAST(quantity AS INT) IS NULL THEN 'cast_failure:quantity'
      WHEN unit_sold_price IS NOT NULL AND TRY_CAST(unit_sold_price AS DECIMAL(18,2)) IS NULL THEN 'cast_failure:unit_sold_price'
      WHEN NOT EXISTS (SELECT 1 FROM {silver}.fact_orders AS fo WHERE fo.order_id = li.order_id) THEN 'orphan_fk:order_id'
      WHEN NOT EXISTS (SELECT 1 FROM {silver}.dim_product AS dp WHERE dp.sku = li.sku) THEN 'orphan_fk:sku'
      ELSE NULL END AS reason
    FROM (
      SELECT item_id, order_id, sku, quantity, unit_sold_price FROM (
    SELECT item_id, order_id, sku, quantity, unit_sold_price, ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY _landed_at DESC) AS rn
    FROM {bronze}.order_items
    WHERE item_id IS NOT NULL
  ) WHERE rn = 1
    ) AS li
  ) AS x
  WHERE x.reason IS NULL
) AS s
ON t.item_id = s.item_id
WHEN MATCHED THEN UPDATE SET
    t.order_id = s.order_id,
    t.sku = s.sku,
    t.quantity = s.quantity,
    t.unit_sold_price = s.unit_sold_price,
    t.line_amount = s.line_amount,
    t._ingested_at = s._ingested_at,
    t._source_table = s._source_table
WHEN NOT MATCHED THEN INSERT (item_id, order_id, sku, quantity, unit_sold_price, line_amount, _ingested_at, _source_table)
VALUES (s.item_id, s.order_id, s.sku, s.quantity, s.unit_sold_price, s.line_amount, s._ingested_at, s._source_table)
"""
spark.sql(STMT_WRITE)

# COMMAND ----------

# Row-count report
print("silver.fact_order_lines rows:", spark.sql(f"SELECT COUNT(*) AS n FROM {silver}.fact_order_lines").collect()[0]["n"])
