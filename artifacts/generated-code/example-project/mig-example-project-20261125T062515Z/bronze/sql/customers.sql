-- bronze/sql/customers.sql : exact statements of the notebook, placeholders resolved for run mig-example-project-20261125T062515Z
-- Execute in order, one statement each.

-- ddl
CREATE TABLE IF NOT EXISTS `retail_demo`.`bronze`.customers (
    customer_id STRING NOT NULL COMMENT 'Source column customer_id from raw_dump.raw_customers, kept as-is',
    full_name STRING COMMENT 'Source column full_name from raw_dump.raw_customers, kept as-is',
    email STRING COMMENT 'Source column email from raw_dump.raw_customers, kept as-is',
    loyalty_tier STRING COMMENT 'Source column loyalty_tier from raw_dump.raw_customers, kept as-is',
    signup_date STRING COMMENT 'Source column signup_date from raw_dump.raw_customers, kept as-is',
    region STRING COMMENT 'Source column region from raw_dump.raw_customers, kept as-is',
    _landed_at TIMESTAMP NOT NULL COMMENT 'Landing load time of the row',
    _ingested_at TIMESTAMP NOT NULL COMMENT 'Load timestamp of the run that wrote this row',
    _source_table STRING NOT NULL COMMENT 'Fully qualified landing table of this row'
)
USING DELTA
COMMENT 'Bronze CRM customers: as-is copy of landing raw_customers, append-only'
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact'   = 'true'
);

-- write
INSERT INTO `retail_demo`.`bronze`.customers (customer_id, full_name, email, loyalty_tier, signup_date, region, _landed_at, _ingested_at, _source_table)
SELECT l.customer_id, l.full_name, l.email, l.loyalty_tier, l.signup_date, l.region, l._landed_at, current_timestamp(), '`retail_demo`.`landing`.raw_customers'
FROM `retail_demo`.`landing`.raw_customers AS l
WHERE l.customer_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM `retail_demo`.`bronze`.customers AS b WHERE b.customer_id = l.customer_id AND b._landed_at = l._landed_at);

