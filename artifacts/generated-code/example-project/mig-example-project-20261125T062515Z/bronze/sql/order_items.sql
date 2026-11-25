-- bronze/sql/order_items.sql : exact statements of the notebook, placeholders resolved for run mig-example-project-20261125T062515Z
-- Execute in order, one statement each.

-- ddl
CREATE TABLE IF NOT EXISTS `retail_demo`.`bronze`.order_items (
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
);

-- write
INSERT INTO `retail_demo`.`bronze`.order_items (item_id, order_id, sku, quantity, unit_sold_price, _landed_at, _ingested_at, _source_table)
SELECT l.item_id, l.order_id, l.sku, l.quantity, l.unit_sold_price, l._landed_at, current_timestamp(), '`retail_demo`.`landing`.raw_order_items'
FROM `retail_demo`.`landing`.raw_order_items AS l
WHERE l.item_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM `retail_demo`.`bronze`.order_items AS b WHERE b.item_id = l.item_id AND b._landed_at = l._landed_at);

