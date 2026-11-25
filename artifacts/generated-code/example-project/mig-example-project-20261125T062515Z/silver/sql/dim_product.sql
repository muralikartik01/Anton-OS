-- silver/sql/dim_product.sql : exact statements of the notebook, placeholders resolved for run mig-example-project-20261125T062515Z
-- Execute in order, one statement each.

-- ddl
CREATE TABLE IF NOT EXISTS `retail_demo`.`silver`.dim_product (
    sku STRING NOT NULL COMMENT 'Business key from the ERP product table',
    product_name STRING COMMENT 'Product name, trimmed',
    category STRING COMMENT 'Product category, trimmed',
    unit_cost DECIMAL(18,2) COMMENT 'Unit cost cast from source string',
    list_price DECIMAL(18,2) COMMENT 'List price cast from source string',
    is_active BOOLEAN COMMENT 'Whether the product is active, cast from source string',
    _ingested_at TIMESTAMP NOT NULL COMMENT 'Load timestamp of the run that wrote this row',
    _source_table STRING NOT NULL COMMENT 'Fully qualified Bronze table of this row'
)
USING DELTA
COMMENT 'Silver product dimension, one row per sku'
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact'   = 'true'
);

-- quarantine
INSERT INTO `retail_demo`.`silver`.quarantine_rows (source_table, record_key, reason, row_json, _run_id, _ingested_at, _source_table)
SELECT '`retail_demo`.`bronze`.products', x.sku, x.reason, TO_JSON(STRUCT(x.sku, x.product_name, x.category, x.unit_cost, x.list_price, x.is_active)), 'mig-example-project-20261125T062515Z', current_timestamp(), '`retail_demo`.`bronze`.products'
FROM (
    SELECT sku, product_name, category, unit_cost, list_price, is_active, CASE
      WHEN unit_cost IS NOT NULL AND TRY_CAST(unit_cost AS DECIMAL(18,2)) IS NULL THEN 'cast_failure:unit_cost'
      WHEN list_price IS NOT NULL AND TRY_CAST(list_price AS DECIMAL(18,2)) IS NULL THEN 'cast_failure:list_price'
      WHEN is_active IS NOT NULL AND TRY_CAST(LOWER(TRIM(is_active)) AS BOOLEAN) IS NULL THEN 'cast_failure:is_active'
      ELSE NULL END AS reason
    FROM (
      SELECT sku, product_name, category, unit_cost, list_price, is_active FROM (
    SELECT sku, product_name, category, unit_cost, list_price, is_active, ROW_NUMBER() OVER (PARTITION BY sku ORDER BY _landed_at DESC) AS rn
    FROM `retail_demo`.`bronze`.products
    WHERE sku IS NOT NULL
  ) WHERE rn = 1
    )
) AS x
WHERE x.reason IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM `retail_demo`.`silver`.quarantine_rows AS q WHERE q.source_table = '`retail_demo`.`bronze`.products' AND q.record_key = x.sku AND q.reason = x.reason AND q._run_id = 'mig-example-project-20261125T062515Z');

-- write
MERGE INTO `retail_demo`.`silver`.dim_product AS t
USING (
  SELECT
    x.sku AS sku,
    TRIM(x.product_name) AS product_name,
    TRIM(x.category) AS category,
    TRY_CAST(x.unit_cost AS DECIMAL(18,2)) AS unit_cost,
    TRY_CAST(x.list_price AS DECIMAL(18,2)) AS list_price,
    TRY_CAST(LOWER(TRIM(x.is_active)) AS BOOLEAN) AS is_active,
    current_timestamp() AS _ingested_at,
    '`retail_demo`.`bronze`.products' AS _source_table
  FROM (
    SELECT sku, product_name, category, unit_cost, list_price, is_active, CASE
      WHEN unit_cost IS NOT NULL AND TRY_CAST(unit_cost AS DECIMAL(18,2)) IS NULL THEN 'cast_failure:unit_cost'
      WHEN list_price IS NOT NULL AND TRY_CAST(list_price AS DECIMAL(18,2)) IS NULL THEN 'cast_failure:list_price'
      WHEN is_active IS NOT NULL AND TRY_CAST(LOWER(TRIM(is_active)) AS BOOLEAN) IS NULL THEN 'cast_failure:is_active'
      ELSE NULL END AS reason
    FROM (
      SELECT sku, product_name, category, unit_cost, list_price, is_active FROM (
    SELECT sku, product_name, category, unit_cost, list_price, is_active, ROW_NUMBER() OVER (PARTITION BY sku ORDER BY _landed_at DESC) AS rn
    FROM `retail_demo`.`bronze`.products
    WHERE sku IS NOT NULL
  ) WHERE rn = 1
    )
  ) AS x
  WHERE x.reason IS NULL
) AS s
ON t.sku = s.sku
WHEN MATCHED THEN UPDATE SET
    t.product_name = s.product_name,
    t.category = s.category,
    t.unit_cost = s.unit_cost,
    t.list_price = s.list_price,
    t.is_active = s.is_active,
    t._ingested_at = s._ingested_at,
    t._source_table = s._source_table
WHEN NOT MATCHED THEN INSERT (sku, product_name, category, unit_cost, list_price, is_active, _ingested_at, _source_table)
VALUES (s.sku, s.product_name, s.category, s.unit_cost, s.list_price, s.is_active, s._ingested_at, s._source_table);

