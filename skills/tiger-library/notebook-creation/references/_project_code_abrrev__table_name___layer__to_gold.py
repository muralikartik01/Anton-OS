# Databricks notebook source
# MAGIC %md
# MAGIC
# MAGIC ## Project Name : < Project_Name >
# MAGIC
# MAGIC ### Purpose
# MAGIC The purpose of this notebook is to read from data foundation Bronze, silver layer and push the data to the gold layer
# MAGIC for the following table
# MAGIC * Gold Table Name
# MAGIC
# MAGIC ### Orignal Creator: < creator_name >
# MAGIC
# MAGIC ### Date Created: < creator_date >
# MAGIC
# MAGIC ### System Id and Reporting Unit ID Details
# MAGIC | System ID | Reporting Unit Id |
# MAGIC | ------ | ------ |
# MAGIC | < systemid > | < ReportingUnitId > |
# MAGIC
# MAGIC ### Version History
# MAGIC
# MAGIC | Date | Author |  Description |
# MAGIC | ------ | ------ | ------ |
# MAGIC | < Date > | < Author > |  < Description > |
# MAGIC
# MAGIC ### Source and Target Info
# MAGIC
# MAGIC #### < Gold Table Name >
# MAGIC
# MAGIC | Source DB  | Source Table |  Target DB | Target Table | Merge Strategy
# MAGIC |------|------ |--------|--------|--------|
# MAGIC |< source_db1 >| < source_table_1 > | < tgt_db_nm >| < tgt_table_1 >  |< Merge Criteria >

# COMMAND ----------

# MAGIC %md
# MAGIC ### Running Utility Notebook

# COMMAND ----------

# MAGIC %run ./notebook_common_utils 

# COMMAND ----------

# MAGIC %md
# MAGIC ### Running Parameter Notebook

# COMMAND ----------

# MAGIC %run ./notebook_common_variables

# COMMAND ----------

# MAGIC %md
# MAGIC ### Importing the Necessary Packages

# COMMAND ----------

import re
import json
from pyspark.sql.functions import *
from datetime import datetime
from cdo_audit_framework_wd_la import audit_utilities as au
from pyspark.sql.types import StringType
from typing import Final
from cdo_dq_framework import dqm_framework

# COMMAND ----------

# MAGIC %md
# MAGIC ### Get values from widgets

# COMMAND ----------

dbutils.widgets.text("additional_params", "{}", "additional_params")
dbutils.widgets.text("dataset_name", "", "")
dbutils.widgets.text("environment", "", "")
dbutils.widgets.text("job_id", "")
dbutils.widgets.text("project_params", "{}", "project_params")
dbutils.widgets.text("source_layer", "", "")
dbutils.widgets.text("table_name", "", "")

additional_params = dbutils.widgets.get("additional_params")
dataset_name = dbutils.widgets.get("dataset_name")
environment = dbutils.widgets.get("environment")
job_id = dbutils.widgets.get("job_id")
project_params = dbutils.widgets.get("project_params")
source_layer = dbutils.widgets.get("source_layer")
target_tbl = dbutils.widgets.get("table_name")

# COMMAND ----------

# MAGIC %md
# MAGIC ### JSON String Document into Python Dictionary

# COMMAND ----------

try:
    project_params = re.sub(":\s*(,|})", ':""\\1', getArgument("project_params"))
    project_params = re.sub("'", '"', project_params)
    project_params = json.loads(project_params)

    additional_params = re.sub(":\s*(,|})", ':""\\1', getArgument("additional_params"))
    additional_params = re.sub("'", '"', additional_params)
    additional_params = json.loads(additional_params)
except Exception as e:
    raise e

# COMMAND ----------

# MAGIC %md
# MAGIC ### Variable declaration

# COMMAND ----------

# System Id and Reporting Unit Id
systemId = project_params["systemId"]
reportingUnitId = project_params["reportingUnitId"]

# DQ checks
dq_enable_flag = additional_params.get("dq_enable_flag", "False")
dq_enable_flag = False if dq_enable_flag.strip().lower() == "false" else True
dq_dataasset_name = additional_params.get("dq_dataasset_name", "")

input_tbls = additional_params.get("input_tbls", [])
market_name = project_params["market"]
gold_database_name = project_params["gold_database_name"]

# p2d_flag
p2d_flag = additional_params.get("p2d_flag", "False")
p2d_flag = False if p2d_flag.strip().lower() == "false" else True

# General Variables
start_time = str(datetime.now())
load_ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
status = "Success"
error_message = None
error_details = None

# Audit Framework
full_notebook_path = (
    dbutils.notebook.entry_point.getDbutils()
    .notebook()
    .getContext()
    .notebookPath()
    .get()
)
notebook_nm = full_notebook_path.split("/")[-1]
notebook_job_url = au.get_notebook_job_url()
product_cd = project_params["product_cd"]

log_additional_context_dict = {
    **project_params,
    **additional_params,
    "gold_dataset_name": dataset_name,
    "source_layer": source_layer,
}

# System and Reporting Unit ID check
sys_rpt_id_config_dict = {
    "XTNDFSystemId": systemId,
    "XTNDFReportingUnitId": reportingUnitId,
}

# Prints
print(f"job_id              : {job_id}")
print(f"dataset_name        : {dataset_name}")
print(f"target_tbl          : {target_tbl}")
print(f"systemId            : {systemId}")
print(f"reportingUnitId     : {reportingUnitId}")
print(f"product_cd          : {product_cd}")
print(f"notebook_nm         : {notebook_nm}")
print(f"adls_target_zone    : {adls_target_zone}")
print(f"source_layer        : {source_layer}")
print(f"input_tbls          : {input_tbls}")
print(f"project_params      : {project_params}")
print(f"additional_params   : {additional_params}")
print(f"market_name         : {market_name}")


# COMMAND ----------

# MAGIC %md
# MAGIC ### Audit Logic - Initialization

# COMMAND ----------

au.log_audit_data(
    environment=environment,
    product_cd=product_cd,
    notebook_nm=notebook_nm,
    notebook_job_url=notebook_job_url,
    start_tms=start_time,
    end_tms=str(datetime.now()),
    status_cd=status_cd_initial,
    msg_desc=f"Gold Notebook process initialized for {target_tbl} table of schema {gold_database_name}",
    adls_target_zone=adls_target_zone,
    target_db_nm=gold_database_name,
    target_table_nm=target_tbl,
    job_id=job_id,
    market_name=market_name,
    additional_context=log_additional_context_dict,
    post_log=post_log,
)

# COMMAND ----------

# MAGIC %md ### Read Data from Foundation Layer

# COMMAND ----------

if status == "Success" and error_message is None:
    try:
        df_dict = read_data_foundation_tables_udf(
            source_table_name_list=input_tbls,
            databricks_scope_name=databricks_scope_name,
            spn_client_id_secret_name=spn_client_id_secret_name,
            spn_tenant_id_secret_name=spn_tenant_id_secret_name,
            spn_client_secret_secret_name=spn_client_secret_secret_name,
            environment=environment,
            p2d_flag=p2d_flag,
        )
        au.log_audit_data(
            environment=environment,
            product_cd=product_cd,
            notebook_nm=notebook_nm,
            notebook_job_url=notebook_job_url,
            start_tms=start_time,
            end_tms=str(datetime.now()),
            status_cd=status_cd_progess,
            msg_desc=f"Transformation started for {target_tbl}....",
            adls_target_zone=adls_target_zone,
            target_db_nm=gold_database_name,
            target_table_nm=target_tbl,
            job_id=job_id,
            market_name=market_name,
            additional_context=log_additional_context_dict,
            post_log=post_log,
        )
    except Exception as e:
        status = "Failed"
        error_message = str(e)
        print(e)
        au.log_audit_data(
            environment=environment,
            product_cd=product_cd,
            notebook_nm=notebook_nm,
            notebook_job_url=notebook_job_url,
            start_tms=start_time,
            end_tms=str(datetime.now()),
            status_cd=status_cd_failure,
            msg_desc=error_message,
            adls_target_zone=adls_target_zone,
            target_db_nm=gold_database_name,
            target_table_nm=target_tbl,
            job_id=job_id,
            market_name=market_name,
            additional_context=log_additional_context_dict,
            post_log=post_log,
        )

# COMMAND ----------

# MAGIC %md
# MAGIC ### Column Renaming and Transformations

# COMMAND ----------

if status == "Success" and error_message is None:
    try:
        df_final = spark.sql(
            """ select
                        <bronze_col1> as <gold_col1>,
                        <bronze_col2> as <gold_col2>,
                        ...,
                        cast{1} as int) as XTNDFSystemId,
                        cast({2} as int) as XTNDFReportingUnitId,
                        to_timestamp('{3}', 'yyyy-MM-dd HH:mm:ss.SSS') as XTNCreatedTime,
                        cast(trim({0}) as string) as XTNCreatedById,
                        to_timestamp('{3}', 'yyyy-MM-dd HH:mm:ss.SSS') as XTNUpdatedTime,
                        cast(trim({0}) as string) as XTNUpdatedById
                      from
                        <Bronze_tbl>_vw
          """.format(
                job_id, systemId, reportingUnitId, load_ts
            )
        )
    except Exception as e:
        error_message = str(e)
        status = "Failed"
        print(e)
        au.log_audit_data(
            environment=environment,
            product_cd=product_cd,
            notebook_nm=notebook_nm,
            notebook_job_url=notebook_job_url,
            start_tms=start_time,
            end_tms=str(datetime.now()),
            status_cd=status_cd_failure,
            msg_desc=error_message,
            adls_target_zone=adls_target_zone,
            target_db_nm=gold_database_name,
            target_table_nm=target_tbl,
            job_id=job_id,
            market_name=market_name,
            additional_context=log_additional_context_dict,
            post_log=post_log,
        )


# COMMAND ----------

# MAGIC %md
# MAGIC ### Validation Check for System ID and Reporting Unit ID

# COMMAND ----------

if status == "Success" and error_message is None:
    if check_for_systemid_reporting_id(df_final, sys_rpt_id_config_dict):
        print("Validation checks for System ID and Reporting ID passed Successfully")
    else:
        print("Validation checks for System ID and Reporting ID failed")
        error_message = "Validation checks for System ID and Reporting ID failed."
        status = "Failed"
        au.log_audit_data(
            environment=environment,
            product_cd=product_cd,
            notebook_nm=notebook_nm,
            notebook_job_url=notebook_job_url,
            start_tms=start_time,
            end_tms=str(datetime.now()),
            status_cd=status_cd_failure,
            msg_desc=error_message,
            adls_target_zone=adls_target_zone,
            target_db_nm=gold_database_name,
            target_table_nm=target_tbl,
            job_id=job_id,
            market_name=market_name,
            additional_context=log_additional_context_dict,
            post_log=post_log,
        )
        raise Exception("Validation Check for System ID and Reporting ID failed")


# COMMAND ----------

# MAGIC %md
# MAGIC ### DQ Framework Implementation

# COMMAND ----------

if dq_enable_flag:
    dq_out = dqm_framework.dq_framework_invoke(
        PIPELINE_ID=job_id,
        JOB_ID=job_id,
        DATASET_NAME=dq_dataasset_name,
        DATASET_LAYER=adls_target_zone,
        PRODUCT_NAME=product_cd,
        spark_session=spark,
        INPUT_DATAFRAME=df_final,
        ENVIRONMENT=environment,
        DQType="Independent",
    )

    dqReturnCode = dq_out[0]["ReturnCode"]
    print(dq_out)
    if dqReturnCode == 0:
        print("DQ Checks completed successfully")
        au.log_audit_data(
            environment=environment,
            product_cd=product_cd,
            notebook_nm=notebook_nm,
            notebook_job_url=notebook_job_url,
            start_tms=start_time,
            end_tms=str(datetime.now()),
            status_cd=status_cd_progess,
            msg_desc=f"Gold Notebook DQ process completed for for {target_tbl} table(s) of schema {gold_database_name}",
            adls_target_zone=adls_target_zone,
            target_db_nm=gold_database_name,
            target_table_nm=target_table_nm,
            job_id=job_id,
            market_name=market_name,
            post_log="yes",
        )
    else:
        print("DQ checks failed")
        au.log_audit_data(
            environment=environment,
            product_cd=product_cd,
            notebook_nm=notebook_nm,
            notebook_job_url=notebook_job_url,
            start_tms=start_time,
            end_tms=str(datetime.now()),
            status_cd=status_cd_progess,
            msg_desc=f"Gold Notebook DQ process failed for {target_tbl} table of schema {gold_database_name} owing to below reason:-\n{e}",
            adls_target_zone=adls_target_zone,
            target_db_nm=gold_database_name,
            target_table_nm=target_table_nm,
            job_id=job_id,
            market_name=market_name,
            post_log=post_log,
        )


# COMMAND ----------

# MAGIC %md
# MAGIC
# MAGIC ### Write to the Gold Zone

# COMMAND ----------

if status == "Success" and error_message is None:
    try:

        ####################################################################################################################################################################################################
        
        ## TODO - Implement the logic to write to gold target table ( Needs to be filled by respective product team)
        
        ####################################################################################################################################################################################################
        
        print("Writing to Gold Completed")

        au.log_audit_data(
            environment=environment,
            product_cd=product_cd,
            notebook_nm=notebook_nm,
            notebook_job_url=notebook_job_url,
            start_tms=start_time,
            end_tms=str(datetime.now()),
            status_cd=status_cd_success,
            msg_desc=f"Successfully loaded the {target_tbl} into gold layer",
            adls_target_zone=adls_target_zone,
            target_db_nm=gold_database_name,
            target_table_nm=target_tbl,
            job_id=job_id,
            market_name=market_name,
            additional_context=log_additional_context_dict,
            post_log=post_log,
        )
    except Exception as e:
        error_message = (
            f"An error occurred while loading the gold table {target_tbl}:" + str(e)
        )
        status = "Failed"
        au.log_audit_data(
            environment=environment,
            product_cd=product_cd,
            notebook_nm=notebook_nm,
            notebook_job_url=notebook_job_url,
            start_tms=start_time,
            end_tms=str(datetime.now()),
            status_cd=status_cd_failure,
            msg_desc=error_message,
            adls_target_zone=adls_target_zone,
            target_db_nm=gold_database_name,
            target_table_nm=target_tbl,
            job_id=job_id,
            market_name=market_name,
            additional_context=log_additional_context_dict,
            post_log=post_log,
        )


# COMMAND ----------

# MAGIC %md ### Capture Statistics

# COMMAND ----------

if status == "Success" and error_message is None:
    try:
        statistics_dict = get_statistics_of_data_loaded(f'{gold_database_name}.{target_tbl}', start_time)
        statistics_dict.update(log_additional_context_dict)

        au.log_audit_data(
            environment=environment,
            product_cd=product_cd,
            notebook_nm=notebook_nm,
            notebook_job_url=notebook_job_url,
            start_tms=start_time,
            end_tms=str(datetime.now()),
            status_cd=status_cd_success,
            msg_desc=f"Created statistics for {target_tbl}",
            adls_target_zone=adls_target_zone,
            target_db_nm=gold_database_name,
            target_table_nm=target_tbl,
            job_id=job_id,
            market_name=market_name,
            additional_context=statistics_dict,
            post_log=post_log,
        )
    except Exception as e:
        error_message = f"An error occurred while creating statistics for {target_tbl}:" + str(e)
        status = "Failed"
        au.log_audit_data(
            environment=environment,
            product_cd=product_cd,
            notebook_nm=notebook_nm,
            notebook_job_url=notebook_job_url,
            start_tms=start_time,
            end_tms=str(datetime.now()),
            status_cd=status_cd_failure,
            msg_desc=error_message,
            adls_target_zone=adls_target_zone,
            target_db_nm=gold_database_name,
            target_table_nm=target_tbl,
            job_id=job_id,
            market_name=market_name,
            additional_context=log_additional_context_dict,
            post_log=post_log,
        )


# COMMAND ----------

# MAGIC %md ### Notebook Exit Parameters

# COMMAND ----------

if status == "Success" and error_message is None:
    notebook_exit_return_parameters(
        job_id=job_id,
        dataset_name=dataset_name,
        table_name=target_tbl,
        notebook_nm=notebook_nm,
        source_layer=source_layer,
        project_params=project_params,
        additional_params=additional_params,
        error_message=error_message,
        error_details=error_details,
    )
else:
    raise Exception(f"{error_message}")
