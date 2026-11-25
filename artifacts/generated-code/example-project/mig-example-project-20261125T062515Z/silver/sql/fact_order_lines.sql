-- silver/sql/fact_order_lines.sql : exact statements of the notebook, placeholders resolved for run mig-example-project-20261125T062515Z
-- Execute in order, one statement each.

-- ddl
CREATE TABLE IF NOT EXISTS `retail_demo`.`silver`.fact_order_lines (
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
);

-- quarantine
INSERT INTO `retail_demo`.`silver`.quarantine_rows (source_table, record_key, reason, row_json, _run_id, _ingested_at, _source_table)
SELECT '`retail_demo`.`bronze`.order_items', x.item_id, x.reason, TO_JSON(STRUCT(x.item_id, x.order_id, x.sku, x.quantity, x.unit_sold_price)), 'mig-example-project-20261125T062515Z', current_timestamp(), '`retail_demo`.`bronze`.order_items'
FROM (
    SELECT li.item_id, li.order_id, li.sku, li.quantity, li.unit_sold_price, CASE
      WHEN quantity IS NOT NULL AND TRY_CAST(quantity AS INT) IS NULL THEN 'cast_failure:quantity'
      WHEN unit_sold_price IS NOT NULL AND TRY_CAST(unit_sold_price AS DECIMAL(18,2)) IS NULL THEN 'cast_failure:unit_sold_price'
      WHEN NOT EXISTS (SELECT 1 FROM `retail_demo`.`silver`.fact_orders AS fo WHERE fo.order_id = li.order_id) THEN 'orphan_fk:order_id'
      WHEN NOT EXISTS (SELECT 1 FROM `retail_demo`.`silver`.dim_product AS dp WHERE dp.sku = li.sku) THEN 'orphan_fk:sku'
      ELSE NULL END AS reason
    FROM (
      SELECT item_id, order_id, sku, quantity, unit_sold_price FROM (
    SELECT item_id, order_id, sku, quantity, unit_sold_price, ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY _landed_at DESC) AS rn
    FROM `retail_demo`.`bronze`.order_items
    WHERE item_id IS NOT NULL
  ) WHERE rn = 1
    ) AS li
) AS x
WHERE x.reason IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM `retail_demo`.`silver`.quarantine_rows AS q WHERE q.source_table = '`retail_demo`.`bronze`.order_items' AND q.record_key = x.item_id AND q.reason = x.reason AND q._run_id = 'mig-example-project-20261125T062515Z');

-- write
MERGE INTO `retail_demo`.`silver`.fact_order_lines AS t
USING (
  SELECT
    x.item_id AS item_id,
    x.order_id AS order_id,
    x.sku AS sku,
    TRY_CAST(x.quantity AS INT) AS quantity,
    TRY_CAST(x.unit_sold_price AS DECIMAL(18,2)) AS unit_sold_price,
    TRY_CAST(x.quantity AS INT) * TRY_CAST(x.unit_sold_price AS DECIMAL(18,2)) AS line_amount,
    current_timestamp() AS _ingested_at,
    '`retail_demo`.`bronze`.order_items' AS _source_table
  FROM (
    SELECT li.item_id, li.order_id, li.sku, li.quantity, li.unit_sold_price, CASE
      WHEN quantity IS NOT NULL AND TRY_CAST(quantity AS INT) IS NULL THEN 'cast_failure:quantity'
      WHEN unit_sold_price IS NOT NULL AND TRY_CAST(unit_sold_price AS DECIMAL(18,2)) IS NULL THEN 'cast_failure:unit_sold_price'
      WHEN NOT EXISTS (SELECT 1 FROM `retail_demo`.`silver`.fact_orders AS fo WHERE fo.order_id = li.order_id) THEN 'orphan_fk:order_id'
      WHEN NOT EXISTS (SELECT 1 FROM `retail_demo`.`silver`.dim_product AS dp WHERE dp.sku = li.sku) THEN 'orphan_fk:sku'
      ELSE NULL END AS reason
    FROM (
      SELECT item_id, order_id, sku, quantity, unit_sold_price FROM (
    SELECT item_id, order_id, sku, quantity, unit_sold_price, ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY _landed_at DESC) AS rn
    FROM `retail_demo`.`bronze`.order_items
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
VALUES (s.item_id, s.order_id, s.sku, s.quantity, s.unit_sold_price, s.line_amount, s._ingested_at, s._source_table);

