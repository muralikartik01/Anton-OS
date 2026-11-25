# Databricks notebook source
# MAGIC %md
# MAGIC # silver.fact_orders
# MAGIC - Purpose: Silver order fact from latest Bronze order per order_id, with line-item total and reconciliation flag
# MAGIC - Source: `{bronze}.orders`, `{bronze}.order_items`, `{silver}.dim_customer`
# MAGIC - Target: `{silver_catalog}.{silver_schema}.fact_orders`
# MAGIC - Load strategy: upsert (MERGE); keys: order_id
# MAGIC - Mapping rows: silver.fact_orders.* (incl. rule-order-status-domain, rule-payment-method-domain, rule-referential-integrity, rule-order-amount-reconciles; OQ1 option a)
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
MERGE_KEYS = ['order_id']
rows_written = 0

# COMMAND ----------

# ddl
STMT_DDL = f"""
CREATE TABLE IF NOT EXISTS {silver}.fact_orders (
    order_id STRING NOT NULL COMMENT 'Business key from the POS order table',
    customer_id STRING NOT NULL COMMENT 'Customer of the order; FK to dim_customer',
    store_id STRING COMMENT 'Store of the order',
    order_timestamp TIMESTAMP_NTZ COMMENT 'Order time cast from source string; no time zone assumed',
    order_status STRING COMMENT 'COMPLETED, RETURNED or CANCELLED',
    payment_method STRING COMMENT 'UPI, CARD or CASH',
    gross_amount DECIMAL(18,2) COMMENT 'Gross order amount cast from source string',
    discount_amount DECIMAL(18,2) COMMENT 'Discount amount cast from source string',
    items_total DECIMAL(18,2) COMMENT 'Sum of quantity times unit_sold_price over the order lines',
    is_amount_reconciled BOOLEAN COMMENT 'gross_amount - discount_amount = items_total per rule-order-amount-reconciles as written; flag only (OQ1 option a)',
    _ingested_at TIMESTAMP NOT NULL COMMENT 'Load timestamp of the run that wrote this row',
    _source_table STRING NOT NULL COMMENT 'Fully qualified Bronze table of this row'
)
USING DELTA
COMMENT 'Silver order fact, one row per order_id'
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
SELECT '{bronze}.orders', x.order_id, x.reason, TO_JSON(STRUCT(x.order_id, x.customer_id, x.store_id, x.order_timestamp, x.order_status, x.payment_method, x.gross_amount, x.discount_amount)), '{run_id}', current_timestamp(), '{bronze}.orders'
FROM (
    SELECT o.order_id, o.customer_id, o.store_id, o.order_timestamp, o.order_status, o.payment_method, o.gross_amount, o.discount_amount,
      CAST(i.items_total AS DECIMAL(18,2)) AS items_total,
      CASE
      WHEN order_timestamp IS NOT NULL AND TRY_CAST(order_timestamp AS TIMESTAMP_NTZ) IS NULL THEN 'cast_failure:order_timestamp'
      WHEN gross_amount IS NOT NULL AND TRY_CAST(gross_amount AS DECIMAL(18,2)) IS NULL THEN 'cast_failure:gross_amount'
      WHEN discount_amount IS NOT NULL AND TRY_CAST(discount_amount AS DECIMAL(18,2)) IS NULL THEN 'cast_failure:discount_amount'
      WHEN NOT COALESCE(TRIM(order_status) IN ('COMPLETED', 'RETURNED', 'CANCELLED'), FALSE) THEN 'domain_violation:rule-order-status-domain'
      WHEN NOT COALESCE(TRIM(payment_method) IN ('UPI', 'CARD', 'CASH'), FALSE) THEN 'domain_violation:rule-payment-method-domain'
      WHEN NOT EXISTS (SELECT 1 FROM {silver}.dim_customer AS d WHERE d.customer_id = o.customer_id) THEN 'orphan_fk:customer_id'
      ELSE NULL END AS reason
    FROM (
      SELECT order_id, customer_id, store_id, order_timestamp, order_status, payment_method, gross_amount, discount_amount FROM (
    SELECT order_id, customer_id, store_id, order_timestamp, order_status, payment_method, gross_amount, discount_amount, ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY _landed_at DESC) AS rn
    FROM {bronze}.orders
    WHERE order_id IS NOT NULL
  ) WHERE rn = 1
    ) AS o
    LEFT JOIN (
      SELECT order_id, SUM(TRY_CAST(quantity AS INT) * TRY_CAST(unit_sold_price AS DECIMAL(18,2))) AS items_total
      FROM (
        SELECT item_id, order_id, quantity, unit_sold_price FROM (
    SELECT item_id, order_id, quantity, unit_sold_price, ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY _landed_at DESC) AS rn
    FROM {bronze}.order_items
    WHERE item_id IS NOT NULL
  ) WHERE rn = 1
      )
      GROUP BY order_id
    ) AS i ON i.order_id = o.order_id
) AS x
WHERE x.reason IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM {silver}.quarantine_rows AS q WHERE q.source_table = '{bronze}.orders' AND q.record_key = x.order_id AND q.reason = x.reason AND q._run_id = '{run_id}')
"""
spark.sql(STMT_QUARANTINE)

# COMMAND ----------

# write
STMT_WRITE = f"""
MERGE INTO {silver}.fact_orders AS t
USING (
  SELECT
    x.order_id AS order_id,
    x.customer_id AS customer_id,
    x.store_id AS store_id,
    TRY_CAST(x.order_timestamp AS TIMESTAMP_NTZ) AS order_timestamp,
    TRIM(x.order_status) AS order_status,
    TRIM(x.payment_method) AS payment_method,
    TRY_CAST(x.gross_amount AS DECIMAL(18,2)) AS gross_amount,
    TRY_CAST(x.discount_amount AS DECIMAL(18,2)) AS discount_amount,
    x.items_total AS items_total,
    CASE WHEN x.items_total IS NULL OR TRY_CAST(x.gross_amount AS DECIMAL(18,2)) IS NULL OR TRY_CAST(x.discount_amount AS DECIMAL(18,2)) IS NULL THEN NULL ELSE (TRY_CAST(x.gross_amount AS DECIMAL(18,2)) - TRY_CAST(x.discount_amount AS DECIMAL(18,2)) = x.items_total) END AS is_amount_reconciled,
    current_timestamp() AS _ingested_at,
    '{bronze}.orders' AS _source_table
  FROM (
    SELECT o.order_id, o.customer_id, o.store_id, o.order_timestamp, o.order_status, o.payment_method, o.gross_amount, o.discount_amount,
      CAST(i.items_total AS DECIMAL(18,2)) AS items_total,
      CASE
      WHEN order_timestamp IS NOT NULL AND TRY_CAST(order_timestamp AS TIMESTAMP_NTZ) IS NULL THEN 'cast_failure:order_timestamp'
      WHEN gross_amount IS NOT NULL AND TRY_CAST(gross_amount AS DECIMAL(18,2)) IS NULL THEN 'cast_failure:gross_amount'
      WHEN discount_amount IS NOT NULL AND TRY_CAST(discount_amount AS DECIMAL(18,2)) IS NULL THEN 'cast_failure:discount_amount'
      WHEN NOT COALESCE(TRIM(order_status) IN ('COMPLETED', 'RETURNED', 'CANCELLED'), FALSE) THEN 'domain_violation:rule-order-status-domain'
      WHEN NOT COALESCE(TRIM(payment_method) IN ('UPI', 'CARD', 'CASH'), FALSE) THEN 'domain_violation:rule-payment-method-domain'
      WHEN NOT EXISTS (SELECT 1 FROM {silver}.dim_customer AS d WHERE d.customer_id = o.customer_id) THEN 'orphan_fk:customer_id'
      ELSE NULL END AS reason
    FROM (
      SELECT order_id, customer_id, store_id, order_timestamp, order_status, payment_method, gross_amount, discount_amount FROM (
    SELECT order_id, customer_id, store_id, order_timestamp, order_status, payment_method, gross_amount, discount_amount, ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY _landed_at DESC) AS rn
    FROM {bronze}.orders
    WHERE order_id IS NOT NULL
  ) WHERE rn = 1
    ) AS o
    LEFT JOIN (
      SELECT order_id, SUM(TRY_CAST(quantity AS INT) * TRY_CAST(unit_sold_price AS DECIMAL(18,2))) AS items_total
      FROM (
        SELECT item_id, order_id, quantity, unit_sold_price FROM (
    SELECT item_id, order_id, quantity, unit_sold_price, ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY _landed_at DESC) AS rn
    FROM {bronze}.order_items
    WHERE item_id IS NOT NULL
  ) WHERE rn = 1
      )
      GROUP BY order_id
    ) AS i ON i.order_id = o.order_id
  ) AS x
  WHERE x.reason IS NULL
) AS s
ON t.order_id = s.order_id
WHEN MATCHED THEN UPDATE SET
    t.customer_id = s.customer_id,
    t.store_id = s.store_id,
    t.order_timestamp = s.order_timestamp,
    t.order_status = s.order_status,
    t.payment_method = s.payment_method,
    t.gross_amount = s.gross_amount,
    t.discount_amount = s.discount_amount,
    t.items_total = s.items_total,
    t.is_amount_reconciled = s.is_amount_reconciled,
    t._ingested_at = s._ingested_at,
    t._source_table = s._source_table
WHEN NOT MATCHED THEN INSERT (order_id, customer_id, store_id, order_timestamp, order_status, payment_method, gross_amount, discount_amount, items_total, is_amount_reconciled, _ingested_at, _source_table)
VALUES (s.order_id, s.customer_id, s.store_id, s.order_timestamp, s.order_status, s.payment_method, s.gross_amount, s.discount_amount, s.items_total, s.is_amount_reconciled, s._ingested_at, s._source_table)
"""
spark.sql(STMT_WRITE)

# COMMAND ----------

# Row-count report
print("silver.fact_orders rows:", spark.sql(f"SELECT COUNT(*) AS n FROM {silver}.fact_orders").collect()[0]["n"])
