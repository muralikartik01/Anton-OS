# Databricks notebook source
# MAGIC %md
# MAGIC # silver.quarantine_rows
# MAGIC - Purpose: creates the Silver quarantine table (rows are inserted by the other Silver notebooks)
# MAGIC - Source: N/A
# MAGIC - Target: `{silver_catalog}.{silver_schema}.quarantine_rows`
# MAGIC - Load strategy: create-only (no data written); keys: source_table,record_key,reason,_run_id
# MAGIC - Mapping rows: silver.quarantine_rows.*
# MAGIC - Run: mig-example-project-20261125T062515Z (approved blueprint, dry-run generation; never executed by this agent)


# COMMAND ----------

dbutils.widgets.text("silver_catalog", "")
dbutils.widgets.text("silver_schema", "")
dbutils.widgets.text("run_id", "")
dbutils.widgets.text("project_id", "")

silver_catalog = dbutils.widgets.get("silver_catalog")
silver_schema = dbutils.widgets.get("silver_schema")
run_id = dbutils.widgets.get("run_id")
project_id = dbutils.widgets.get("project_id")

# COMMAND ----------

silver = f"`{silver_catalog}`.`{silver_schema}`"
LOAD_STRATEGY = "create-only"
MERGE_KEYS = ['source_table', 'record_key', 'reason', '_run_id']
rows_written = 0

# COMMAND ----------

# ddl
STMT_DDL = f"""
CREATE TABLE IF NOT EXISTS {silver}.quarantine_rows (
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
)
"""
spark.sql(STMT_DDL)

# COMMAND ----------

# Row-count report
print("silver.quarantine_rows rows:", spark.sql(f"SELECT COUNT(*) AS n FROM {silver}.quarantine_rows").collect()[0]["n"])
