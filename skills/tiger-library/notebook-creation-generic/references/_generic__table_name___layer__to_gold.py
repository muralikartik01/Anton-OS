# Databricks notebook source
# MAGIC %md
# MAGIC
# MAGIC ## Notebook Name: <notebook_name>
# MAGIC
# MAGIC ### Purpose
# MAGIC Reads from source layer(s) and loads data into the gold table:
# MAGIC * **Gold Table**: <catalog.schema.table_name>
# MAGIC
# MAGIC ### Original Creator: <creator_name>
# MAGIC
# MAGIC ### Date Created: <YYYY-MM-DD>
# MAGIC
# MAGIC ### Version History
# MAGIC
# MAGIC | Date | Author | Description | ADO Ref |
# MAGIC |------|--------|-------------|---------|
# MAGIC | <YYYY-MM-DD> | <author> | Initial creation | <US-XXXXX> |
# MAGIC
# MAGIC ### Source and Target Info
# MAGIC
# MAGIC | Source Schema | Source Table | Target Catalog.Schema | Target Table | Load Strategy |
# MAGIC |---------------|-------------|----------------------|--------------|---------------|
# MAGIC | <source_schema> | <source_table> | <catalog.schema> | <target_table> | <Upsert / Append / Delete-Insert> |

# COMMAND ----------

# MAGIC %md
# MAGIC ### Importing the Necessary Packages

# COMMAND ----------

import json
from datetime import datetime
from delta.tables import DeltaTable
from pyspark.sql.functions import lit, to_timestamp, cast

# COMMAND ----------

# MAGIC %md
# MAGIC ### Widget Parameters

# COMMAND ----------

# Widget parameters (job_id injected by Workflows; others have safe defaults for interactive runs)
dbutils.widgets.text("job_id",        "",                                                         "job_id")
dbutils.widgets.text("run_id",        "manual_run",                                               "run_id")
dbutils.widgets.text("pipeline_name", "<pipeline_name>",                                          "pipeline_name")
dbutils.widgets.text("run_ts",        datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],   "run_ts")

job_id        = dbutils.widgets.get("job_id")        or "manual_job"
run_id        = dbutils.widgets.get("run_id")        or "manual_run"
pipeline_name = dbutils.widgets.get("pipeline_name") or "<pipeline_name>"
run_ts        = dbutils.widgets.get("run_ts")        or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

# COMMAND ----------

# MAGIC %md
# MAGIC ### Variable Declaration — Input / Output Tables

# COMMAND ----------

# ---------------------------------------------------------------------------
# environment   : derived from cluster tags — wrapped in try/except for robustness
# target_tbl    : gold target table name (populated from STTM — do not change)
# AUDIT_TABLE   : fully qualified Delta table for run-status logging
# INPUT_TABLES  : source tables — wrap catalog name in backticks if it contains hyphens
# GOLD_DB       : catalog.schema prefix for the gold target
# MERGE_KEYS    : columns used in the MERGE ON condition (Upsert only)
# ---------------------------------------------------------------------------

# Derive environment from cluster tags — wrapped in try/except for robustness across all cluster types
try:
    cluster_tags = spark.conf.get("spark.databricks.clusterUsageTags.clusterAllTags", "")
    environment  = cluster_tags.split("_")[0] if cluster_tags else "dev"
except Exception:
    environment  = "dev"

# Target table name — set from STTM, no widget required
target_tbl    = "<table_name_snake_case>"

# Audit table — wrap catalog name in backticks if it contains hyphens (e.g. `my-catalog`)
AUDIT_TABLE   = "`<catalog>`.<audit_schema>.pipeline_audit_log"

# Source and target paths — wrap catalog names in backticks when they contain hyphens
INPUT_TABLES  = [
    "`<catalog>`.<source_schema>.<source_table_1>",
    # "`<catalog>`.<source_schema>.<source_table_2>",   # add more as needed
]
GOLD_DB       = "`<catalog>`.<gold_schema>"
MERGE_KEYS    = ["<merge_key_col_1>", "<merge_key_col_2>"]   # empty list → Append strategy

# Runtime metadata
start_time    = str(datetime.utcnow())
load_ts       = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
status        = "Success"
error_message = None
rows_written  = 0

print("Defined variables:")
for var in [
    "environment", "target_tbl", "AUDIT_TABLE", "INPUT_TABLES", "GOLD_DB",
    "MERGE_KEYS", "LOAD_STRATEGY", "start_time", "load_ts", "status",
    "error_message", "rows_written", "job_id",
]:
    print(f"{var}: {locals()[var]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Read Data from Source Tables

# COMMAND ----------

if status == "Success" and error_message is None:
    try:
        # Register each source table as a temp view for use in the transformation SQL
        for tbl in INPUT_TABLES:
            alias = tbl.split(".")[-1]          # use the table name portion as the view name
            spark.table(tbl).createOrReplaceTempView(alias)
            print(f"Registered temp view '{alias}' from {tbl}")
    except Exception as e:
        status        = "Failed"
        error_message = f"Failed to read source tables: {str(e)}"
        print(error_message)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Transformation SQL (Column Renaming and Mapping)

# COMMAND ----------

if status == "Success" and error_message is None:
    try:
        df_final = spark.sql(
            """
            SELECT
                -- Business columns (CAST(<source_col> AS <type>) AS <TargetCol>)
                CAST(<source_col_1> AS STRING)          AS <target_col_1>,
                CAST(<source_col_2> AS DECIMAL(18, 2))  AS <target_col_2>,
                CASE
                    WHEN <condition> THEN <value_a>
                    ELSE <value_b>
                END                                     AS <derived_target_col>,

                -- Audit columns
                TO_TIMESTAMP('{load_ts}', 'yyyy-MM-dd HH:mm:ss.SSS')   AS XTNCreatedTime,
                CAST(TRIM('{job_id}') AS STRING)                        AS XTNCreatedById,
                TO_TIMESTAMP('{load_ts}', 'yyyy-MM-dd HH:mm:ss.SSS')   AS XTNUpdatedTime,
                CAST(TRIM('{job_id}') AS STRING)                        AS XTNUpdatedById

            FROM <source_table_view>
            -- INNER JOIN <dimension_view> ON <source_table_view>.<pk> = <dimension_view>.<fk>
            -- WHERE <filter_condition>
            """.format(
                load_ts      = load_ts,
                job_id       = job_id,
            )
        )
    except Exception as e:
        status        = "Failed"
        error_message = f"Transformation failed for {target_tbl}: {str(e)}"
        print(error_message)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Write to Target Table (Load Strategy)
# MAGIC
# MAGIC Strategy is auto-detected from STTM:
# MAGIC * **Upsert** — `MERGE_KEYS` list is non-empty → DeltaTable MERGE INTO
# MAGIC * **Append** — `MERGE_KEYS` is empty list
# MAGIC * **Delete-Insert** — Set `LOAD_STRATEGY = "delete-insert"` in variable block above

# COMMAND ----------

LOAD_STRATEGY = "upsert"       # options: "upsert" | "append" | "delete-insert"
                               # Overridden by agent based on STTM pattern

if status == "Success" and error_message is None:
    try:
        full_target = f"{GOLD_DB}.{target_tbl}"

        if LOAD_STRATEGY == "upsert" and MERGE_KEYS:
            merge_condition = " AND ".join([f"tgt.{k} = src.{k}" for k in MERGE_KEYS])
            delta_table = DeltaTable.forName(spark, full_target)
            delta_table.alias("tgt").merge(
                df_final.alias("src"),
                merge_condition,
            ).whenMatchedUpdateAll(
            ).whenNotMatchedInsertAll(
            ).execute()
            print(f"Upsert completed into {full_target} on keys: {MERGE_KEYS}")

        elif LOAD_STRATEGY == "append":
            df_final.write.format("delta").mode("append").saveAsTable(full_target)
            print(f"Append completed into {full_target}")

        elif LOAD_STRATEGY == "delete-insert":
            spark.sql(f"TRUNCATE TABLE {full_target}")
            df_final.write.format("delta").mode("append").saveAsTable(full_target)
            print(f"Delete-Insert completed into {full_target}")

        else:
            raise ValueError(
                f"Unknown LOAD_STRATEGY='{LOAD_STRATEGY}'. "
                "Expected: 'upsert', 'append', or 'delete-insert'."
            )

        rows_written = spark.table(full_target).count()
        print(f"Rows in target after load: {rows_written}")

    except Exception as e:
        status        = "Failed"
        error_message = f"Write to {target_tbl} failed: {str(e)}"
        print(error_message)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Audit Log — Write Run Status to Delta Audit Table

# COMMAND ----------

try:
    end_time  = str(datetime.utcnow())
    audit_row = [{
        "notebook_name": dbutils.notebook.entry_point.getDbutils()
                         .notebook().getContext().notebookPath().get().split("/")[-1],
        "run_timestamp": load_ts,
        "environment":   environment,
        "target_table":  f"{GOLD_DB}.{target_tbl}",
        "load_strategy": LOAD_STRATEGY,
        "rows_written":  int(rows_written),
        "job_id":        str(job_id),
        "status":        str(status),
        "error_message": str(error_message) if error_message else "",
        "start_time":    str(start_time),
        "end_time":      str(end_time),
    }]

    schema = (
        "notebook_name STRING, run_timestamp STRING, environment STRING, "
        "target_table STRING, load_strategy STRING, rows_written INT, "
        "job_id STRING, status STRING, error_message STRING, "
        "start_time STRING, end_time STRING"
    )

    (
        spark.createDataFrame(audit_row, schema)
        .write
        .format("delta")
        .mode("append")
        .saveAsTable(AUDIT_TABLE)
    )
    print(f"Audit row written to {AUDIT_TABLE} — status={status}")

except Exception as audit_exc:
    # Audit failure must not mask a successful load; log to stdout only
    print(f"WARNING: Audit log write failed (non-fatal): {str(audit_exc)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Notebook Exit

# COMMAND ----------

exit_payload = json.dumps({
    "status":        status,
    "target_table":  f"{GOLD_DB}.{target_tbl}",
    "rows_written":  rows_written,
    "error_message": error_message if error_message else "",
})

if status == "Success" and error_message is None:
    print(f"Notebook completed successfully. Exit payload: {exit_payload}")
    dbutils.notebook.exit(exit_payload)
else:
    print(f"Notebook failed. Exit payload: {exit_payload}")
    raise Exception(error_message)
