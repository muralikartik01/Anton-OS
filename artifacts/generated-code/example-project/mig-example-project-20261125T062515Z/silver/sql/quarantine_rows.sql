-- silver/sql/quarantine_rows.sql : exact statements of the notebook, placeholders resolved for run mig-example-project-20261125T062515Z
-- Execute in order, one statement each.

-- ddl
CREATE TABLE IF NOT EXISTS `retail_demo`.`silver`.quarantine_rows (
    source_table STRING NOT NULL COMMENT 'Bronze table the rejected row came from',
    record_key STRING NOT NULL COMMENT 'Business key of the rejected row',
    reason STRING NOT NULL COMMENT 'cast_failure:<col> | domain_violation:<rule id> | orphan_fk:<col>',
    row_json STRING COMMENT 'TO_JSON of the rejected Bronze row',
    _run_id STRING NOT NULL COMMENT 'Run that quarantined the row',
    _ingested_at TIMESTAMP NOT NULL COMMENT 'Load timestamp of the run that wrote this row',
    _source_table STRING NOT NULL COMMENT 'Fully qualified Bronze table of this row'
)
USING DELTA
COMMENT 'Silver quarantine: rows rejected by cast, domain or foreign-key checks, never silently dropped'
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact'   = 'true'
);

