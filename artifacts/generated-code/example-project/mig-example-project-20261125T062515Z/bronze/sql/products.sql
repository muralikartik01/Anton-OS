-- bronze/sql/products.sql : exact statements of the notebook, placeholders resolved for run mig-example-project-20261125T062515Z
-- Execute in order, one statement each.

-- ddl
CREATE TABLE IF NOT EXISTS `retail_demo`.`bronze`.products (
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
);

-- write
INSERT INTO `retail_demo`.`bronze`.products (sku, product_name, category, unit_cost, list_price, is_active, _landed_at, _ingested_at, _source_table)
SELECT l.sku, l.product_name, l.category, l.unit_cost, l.list_price, l.is_active, l._landed_at, current_timestamp(), '`retail_demo`.`landing`.raw_products'
FROM `retail_demo`.`landing`.raw_products AS l
WHERE l.sku IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM `retail_demo`.`bronze`.products AS b WHERE b.sku = l.sku AND b._landed_at = l._landed_at);

