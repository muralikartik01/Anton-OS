# Databricks notebook source
# MAGIC %md
# MAGIC ## OVERVIEW
# MAGIC 1. The purpose of this notebook is to unit test the notebook {{MAIN_NOTEBOOK_PATH}}
# MAGIC for the table {{TABLE_NAME}}.
# MAGIC 2. Data Asset Name: {{DATA_ASSET_NAME}}
# MAGIC 3. **File Format**: Databricks Python notebook (.py) with magic commands
# MAGIC 4. **Naming Convention**: test_{{ACTUAL_NOTEBOOK_NAME}}.py
# MAGIC
# MAGIC ### Version History
# MAGIC
# MAGIC | S. No | Author |  Date |  Desc |
# MAGIC | ------ | ------ | ------ | ------ |
# MAGIC | 1 | System Generated | {{CURRENT_DATE}} | Initial unit test notebook creation |
# MAGIC 
# MAGIC ---
# MAGIC 
# MAGIC # Unit Test Notebook
# MAGIC This notebook tests the functionality of the target notebook using sample data and validates the output.
# MAGIC 
# MAGIC ## Template Workflow:
# MAGIC 1. **Create Test Data** - Set up temporary views with sample data
# MAGIC 2. **Configure Notebook Parameters** - Define notebook configuration  
# MAGIC 3. **Execute Target Notebook** - Run the notebook being tested
# MAGIC 4. **Define Unit Tests** - Create test functions for validation
# MAGIC 5. **Execute Unit Tests** - Run all test functions and return results
# MAGIC 
# MAGIC ## Template Variables:
# MAGIC - `{{SAMPLE_DATA_FRAMES}}` - Inline DataFrame creation code for each source table
# MAGIC - `{{MAIN_NOTEBOOK_PATH}}` - Path to notebook being tested
# MAGIC - `{{NOTEBOOK_CONFIG}}` - Configuration object for the notebook
# MAGIC - `{{TEST_FUNCTIONS}}` - Custom test function definitions

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Create Sample Test Data
# MAGIC Create inline DataFrames with representative sample data and register as global temp views.
# MAGIC No external file dependencies (ADLS / CSV) required.

# COMMAND ----------

# Step 1: Create inline sample DataFrames and register as global temp views
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, LongType, DoubleType, DateType, TimestampType, BooleanType
from datetime import date, datetime

{{SAMPLE_DATA_FRAMES}}

print("\n📊 Sample data creation complete.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Configure Notebook Parameters
# MAGIC Set up the configuration for the notebook being tested.

# COMMAND ----------

# Step 2: Configure notebook parameters
import json
import uuid

main_notebook_path = "{{MAIN_NOTEBOOK_PATH}}"
notebook_config = {{NOTEBOOK_CONFIG}}

# Automatically add required test parameters
notebook_config["env"] = "dev"
notebook_config["IS_UNIT_TEST"] = "Y"

job_id = f'unit_test_execution_{str(uuid.uuid4())[:8]}'

print("Notebook Configuration:")
print(json.dumps(notebook_config, indent=2))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Execute Target Notebook
# MAGIC Run the notebook being tested with the configured parameters.

# COMMAND ----------

# Step 3: Execute the target notebook
print(f"Executing notebook: {main_notebook_path}")
print("This may take a few minutes...")

try:
    result = dbutils.notebook.run(main_notebook_path, 0, {
        "notebook_config": json.dumps(notebook_config), 
        "job_id": job_id
    })
    print("Notebook execution completed successfully")
    print(f"Notebook result: {result}")
except Exception as e:
    print(f"Notebook execution failed: {str(e)}")
    raise e

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Define Unit Tests
# MAGIC Create test functions to validate the output data in `global_temp.final_view`.
# MAGIC 
# MAGIC **Important:** All unit tests must query `global_temp.final_view` - the standard output table.
# MAGIC Test functions should be generated based on analysis of the target notebook's business logic.

# COMMAND ----------

# Step 4: Define unit tests
test_results = []

def test_row_count():
    """Test that the output has the expected number of rows"""
    df = spark.sql("SELECT * FROM global_temp.final_view")
    row_count = df.count()
    expected_count = 3  # TODO: Update this with actual expected row count from your test data
    print(f"Row count: {row_count}")
    assert row_count == expected_count, f"Expected {expected_count} rows, but got {row_count}"
    print(f"✅ Row count validation passed: {row_count} rows")

{{TEST_FUNCTIONS}}

# Collect all test functions
tests = [test_row_count{{ADDITIONAL_TESTS}}]

print(f"Defined {len(tests)} test functions:")
for test in tests:
    print(f"- {test.__name__}")

for test in tests:
   try:
       test()
       test_results.append((test.__name__, "passed"))
   except Exception as e:
       test_results.append((test.__name__, f"failed: {str(e)}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Aggregate Test Results
# MAGIC
# MAGIC Calculate the summary statistics for the tests.

# COMMAND ----------

# Step 4: Aggregate test results
total = len(tests)
passed = sum(1 for _, status in test_results if status == "passed")
failed = total - passed

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5: Return Results
# MAGIC
# MAGIC Exit the notebook with a JSON string containing test results.

# COMMAND ----------

# Step 5: Return as JSON string
dbutils.notebook.exit(json.dumps({
   "total": total,
   "passed": passed,
   "failed": failed,
   "details": test_results
}))
