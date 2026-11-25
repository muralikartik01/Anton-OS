-- bronze/sql/orders.sql : exact statements of the notebook, placeholders resolved for run mig-example-project-20261125T062515Z
-- Execute in order, one statement each.

-- ddl
CREATE TABLE IF NOT EXISTS `retail_demo`.`bronze`.orders (
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
);

-- write
INSERT INTO `retail_demo`.`bronze`.orders (order_id, customer_id, store_id, order_timestamp, order_status, payment_method, gross_amount, discount_amount, _landed_at, _ingested_at, _source_table)
SELECT l.order_id, l.customer_id, l.store_id, l.order_timestamp, l.order_status, l.payment_method, l.gross_amount, l.discount_amount, l._landed_at, current_timestamp(), '`retail_demo`.`landing`.raw_orders'
FROM `retail_demo`.`landing`.raw_orders AS l
WHERE l.order_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM `retail_demo`.`bronze`.orders AS b WHERE b.order_id = l.order_id AND b._landed_at = l._landed_at);

