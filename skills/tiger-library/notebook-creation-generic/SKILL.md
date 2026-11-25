---
name: notebook-creation-generic
description: >-
  Generate a simplified, standalone Databricks .py notebook for any Silver-to-Gold
  or Bronze-to-Gold ETL pipeline, no %run
  utility notebooks. Uses direct spark.read.table() reads, a plain Delta audit
  write, and a Spark SQL transformation block derived from an STTM CSV. Use this
  skill when the user asks for a generic, lightweight, simple, or standalone
  Databricks notebook without the full Tiger framework stack. Distinct trigger
  phrases: "generic notebook", "simple notebook", "generic etl", "quick notebook",
  "standalone notebook", "lightweight notebook", "create generic notebook",
  "generic gold", "simple etl", "notebook template", "basic notebook".
---

# Notebook Creation Generic Skill — Simplified Databricks Notebook (.py)

## Purpose
Generate a simplified, **framework-independent** Databricks notebook `.py` file
for Silver-to-Gold or Bronze-to-Gold ETL pipelines.

The output template is:
`references/_generic__table_name___layer__to_gold.py`

STTM column mappings are read from `Output/STTM_DDL_creation/`.

---

## Distinct Activation Keywords

Use this skill (NOT `notebook-creation`) when the user says:

`generic notebook` · `simple notebook` · `generic etl` · `quick notebook` ·
`standalone notebook` · `lightweight notebook` · `create generic notebook` ·
`generic gold` · `simple etl` · `notebook template` · `basic notebook`

---

## Reference Files

| File | Purpose | When to Read |
|------|---------|-------------|
| `references/_generic__table_name___layer__to_gold.py` | Base template — all generated notebooks extend this | Before every generation run |
| `Output/STTM_DDL_creation/*.csv` | Source of truth for column mappings, merge keys, and transformations | Every generation run |
| `Output/STTM_DDL_creation/*.sql` | DDL for target table structure validation | Cross-check data types |

---

## Inputs Required

| Input | Source | Example |
|-------|--------|---------|
| Target Table Name | STTM → `Target Table Name*` column | `OperationalExpenseInvoiceFlattened` |
| Gold Database (catalog.schema) | STTM → `Target Data Lake*` column | `uc_prod_snt_gld_01.snp_common_transactions` |
| Source Tables | STTM → `Source Schema Name` + `Source Table name` | `fdn_supplier.XTNBusinessTravelFlightReservation` |
| Merge Keys | STTM → `Merge Key` = `Yes` columns | `InvoiceSourceName`, `ProductKey` |
| Load Strategy | Derived from STTM merge key pattern | `upsert` / `append` / `delete-insert` |
| Audit Table | Variable — defined in variable block | `` `<catalog>`.<audit_schema>.pipeline_audit_log `` |
| Creator Name | User or default `[TO BE UPDATED]` | `Jane Doe` |

---

## STTM Parsing Instructions

The STTM CSV is the single source of truth for column mappings.

### Column Reference

| STTM Column | Notebook Location | How It's Used |
|-------------|------------------|--------------|
| `Source Schema Name` | Header doc + `INPUT_TABLES` | Full Unity Catalog path of source |
| `Source Table name` | Header doc + SQL FROM clause | Source table name / temp view alias |
| `Column Name*` | SQL SELECT source expression | Source column, or compound expression if Derived |
| `Data Transformation Rules*` | SQL SELECT expression | Copied verbatim; CASE WHEN → inline in SQL |
| `Target Column*` | SQL column alias (`AS`) | Gold column name |
| `Target Data Type*` | `CAST(... AS ...)` in SQL | Wraps expression in CAST |
| `Allow Nulls*` | SQL comment | `NOT NULL` → note in comment above column |
| `Merge Key` = `Yes` | `MERGE_KEYS` list + MERGE ON | Part of the MERGE ON condition |
| `Primary Key` = `Yes` | Header documentation | Cross-reference for uniqueness |
| `Target Data Lake*` | `GOLD_DB` variable | Unity Catalog `catalog.schema` prefix |
| `Target Table Name*` | `target_tbl` variable (from STTM) | Gold Delta table name |
| `Default Value` | SQL literal or constant | Used when `Source Name` has no source column |
| `Source Name` = `Derived` | Derived column in SQL | Expression built from `Data Transformation Rules*` |
| `FK Table.columnname` | JOIN clause | `INNER JOIN {fk_table} ON {pk} = {fk}` |

### Load Strategy Detection

| STTM Pattern | Strategy | Write Logic |
|---|---|---|
| `Merge Key` = `Yes` columns present | **upsert** | `DeltaTable.merge(...).whenMatchedUpdateAll().whenNotMatchedInsertAll()` |
| No `Merge Key`, only `Primary Key` | **append** | `df.write.format("delta").mode("append")` |
| Full reload / no keys | **delete-insert** | `TRUNCATE TABLE {target}` then append |

### FK Joins
For each populated `FK Table.columnname` cell: generate
`INNER JOIN {fk_table} ON {source_view}.{pk} = {fk_table}.{fk_col}`.

### Filters
Check `Comments` column: `Source filter:` → add to `WHERE` clause;
`latest` / `ROW_NUMBER()` → add window function with `PARTITION BY` / `ORDER BY`.

### Derived Columns
When `Source Name = Derived`: copy `Data Transformation Rules*` verbatim as the SQL
expression, then wrap with `CAST(... AS <Target Data Type*>) AS <Target Column*>`.

### Data Type Mappings

| STTM Type | Databricks SQL Type |
|-----------|-------------------|
| `string` | `STRING` |
| `date` | `DATE` |
| `timestamp` | `TIMESTAMP` |
| `decimal(p,s)` | `DECIMAL(p,s)` |
| `int` / `bigint` | `INT` / `BIGINT` |
| `boolean` | `BOOLEAN` |

---

## Notebook Generation Process

### Step 1 — Parse STTM
1. Read the STTM CSV from `Output/STTM_DDL_creation/`
2. Extract sources, target, merge keys, and transformations
3. Detect load strategy from merge key pattern
4. Write the finished `.py` notebook to `Output/CodeGeneration/`

### Step 2 — Populate Header
Fill in the `%md` header cell:
```
## Notebook Name: <notebook_file_name>
### Purpose: Reads from source layer(s) and loads <catalog.schema.target_table>
### Original Creator: <name or [TO BE UPDATED]>
### Date Created: <today>
### Source and Target Info: from STTM, with load strategy noted
```

### Step 3 — Imports
Only standard-library and PySpark imports — no PepsiCo packages:
```python
import json
from datetime import datetime
from delta.tables import DeltaTable
from pyspark.sql.functions import lit, to_timestamp, cast
```

### Step 4 — Widget Parameters (5 Widgets)
Five widgets are declared with `or` fallbacks so the notebook runs safely in both Workflows and interactive mode.
The fifth widget `IS_UNIT_TEST` enables the unit-test execution path (redirect reads + write to `_unit_test` table).
```python
dbutils.widgets.text("job_id",        "",               "job_id")
dbutils.widgets.text("run_id",        "manual_run",     "run_id")
dbutils.widgets.text("pipeline_name", "<pipeline_name>","pipeline_name")
dbutils.widgets.text("run_ts",        "",               "run_ts")
dbutils.widgets.text("IS_UNIT_TEST",  "N",              "IS_UNIT_TEST")

job_id        = dbutils.widgets.get("job_id")        or "manual_job"
run_id        = dbutils.widgets.get("run_id")        or "manual_run"
pipeline_name = dbutils.widgets.get("pipeline_name") or "<pipeline_name>"
run_ts        = dbutils.widgets.get("run_ts")        or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
IS_UNIT_TEST  = dbutils.widgets.get("IS_UNIT_TEST")  or "N"
```

### Step 5 — Variable Declaration
Replace all `<placeholders>` with actual values from the STTM.
> **Backtick rule**: catalog names containing hyphens (e.g. `dba-agentic-catalog`) **must** be wrapped in backticks in every string where they appear as a SQL identifier.
```python
# Derive environment — wrapped in try/except for robustness across all cluster types
try:
    cluster_tags = spark.conf.get("spark.databricks.clusterUsageTags.clusterAllTags", "")
    environment  = cluster_tags.split("_")[0] if cluster_tags else "dev"
except Exception:
    environment  = "dev"

target_tbl    = "<table_name_snake_case>"           # from STTM Target Table Name*

# Wrap catalog name in backticks if it contains hyphens (e.g. `my-catalog`)
AUDIT_TABLE   = "`<catalog>`.<audit_schema>.pipeline_audit_log"
INPUT_TABLES  = ["`<catalog>`.<source_schema>.<source_table>"]  # from STTM
GOLD_DB       = "`<catalog>`.<gold_schema>"        # from STTM Target Data Lake*
MERGE_KEYS    = ["key_col_1", "key_col_2"]          # from STTM Merge Key = Yes
LOAD_STRATEGY = "upsert"                            # detected from merge key pattern
```

### Step 6 — Read Source Tables
Register every entry in `INPUT_TABLES` as a temp view using the table-name portion as the alias.
When `IS_UNIT_TEST == "Y"`, bridge the `global_temp` views pre-registered by the test notebook instead
of reading from the actual catalog, so the notebook stays fully offline during testing:
```python
for tbl in INPUT_TABLES:
    alias = tbl.split(".")[-1].strip("`")   # table name portion, backtick-stripped
    if IS_UNIT_TEST == "Y":
        # Unit-test mode: sample data is pre-registered in global_temp by the test notebook.
        # Bridge global_temp.<alias> → local temp view so the transformation SQL can use the
        # plain alias without modification.
        spark.sql(f"CREATE OR REPLACE TEMP VIEW `{alias}` AS SELECT * FROM global_temp.`{alias}`")
        print(f"Unit-test mode: bridged global_temp.{alias} → local temp view '{alias}'")
    else:
        spark.table(tbl).createOrReplaceTempView(alias)
        print(f"Registered temp view '{alias}' from {tbl}")
```
Wrap in `try/except`; on failure set `status = "Failed"` and `error_message = str(e)`.

### Step 7 — Transformation SQL
Build the `spark.sql(""" SELECT ... """)` block from STTM mappings.

Always append these **Mandatory Audit Columns** at the end of the SELECT:

| Target Column | SQL Expression |
|---------------|---------------|
| `XTNCreatedTime` | `TO_TIMESTAMP('{load_ts}', 'yyyy-MM-dd HH:mm:ss.SSS')` |
| `XTNCreatedById` | `CAST(TRIM('{job_id}') AS STRING)` |
| `XTNUpdatedTime` | `TO_TIMESTAMP('{load_ts}', 'yyyy-MM-dd HH:mm:ss.SSS')` |
| `XTNUpdatedById` | `CAST(TRIM('{job_id}') AS STRING)` |

Use `.format(load_ts=load_ts, job_id=job_id)`
to inject runtime variables — no f-strings inside SQL strings.

Wrap in `try/except`; on failure set `status = "Failed"` and `error_message = str(e)`.

### Step 8 — Write to Target

Always check `IS_UNIT_TEST` first. When `"Y"`, write to a separate `_unit_test`-suffixed Delta table
with overwrite so the production gold table is never touched during test runs. The unit test notebook
will query this `_unit_test` table directly.

#### Unit-Test Mode (always first)
```python
if IS_UNIT_TEST == "Y":
    unit_test_target = f"{GOLD_DB}.{target_tbl}_unit_test"
    df_final.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(unit_test_target)
    rows_written = spark.table(unit_test_target).count()
    print(f"Unit-test mode: wrote {rows_written} rows to {unit_test_target} (production table untouched)")
```

#### Upsert (production)
```python
elif LOAD_STRATEGY == "upsert" and MERGE_KEYS:
    merge_condition = " AND ".join([f"tgt.{k} = src.{k}" for k in MERGE_KEYS])
    DeltaTable.forName(spark, full_target).alias("tgt").merge(
        df_final.alias("src"), merge_condition
    ).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()
    rows_written = spark.table(full_target).count()
```

#### Append (production)
```python
elif LOAD_STRATEGY == "append":
    df_final.write.format("delta").mode("append").saveAsTable(full_target)
    rows_written = spark.table(full_target).count()
```

#### Delete-Insert (production)
```python
elif LOAD_STRATEGY == "delete-insert":
    spark.sql(f"TRUNCATE TABLE {full_target}")
    df_final.write.format("delta").mode("append").saveAsTable(full_target)
    rows_written = spark.table(full_target).count()
```

Wrap the entire block in `try/except`; on failure set `status = "Failed"` and `error_message = str(e)`.

### Step 9 — Audit Log Write
Write a single-row audit record to the `AUDIT_TABLE` variable (no widget input required):
```python
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
spark.createDataFrame(audit_row, schema).write.format("delta").mode("append").saveAsTable(AUDIT_TABLE)
```
Wrap in `try/except` — audit failure is **non-fatal** (print warning only, do not override `status`).

### Step 10 — Notebook Exit
```python
exit_payload = json.dumps({"status": status, "target_table": ..., "rows_written": ..., "error_message": ...})
if status == "Success" and error_message is None:
    dbutils.notebook.exit(exit_payload)
else:
    raise Exception(error_message)
```

---

## Full Notebook Structure (10 Sections)

```
1.  [MAGIC %md]  Header Documentation Cell
2.  [python]     Imports (stdlib + pyspark only — no PepsiCo packages)
3.  [MAGIC %md]  Widget Parameters
4.  [python]     5 × dbutils.widgets.text() + dbutils.widgets.get() with or-fallbacks
                 (job_id, run_id, pipeline_name, run_ts, IS_UNIT_TEST)
5.  [MAGIC %md]  Variable Declaration — Input / Output Tables
6.  [python]     INPUT_TABLES, GOLD_DB, MERGE_KEYS, LOAD_STRATEGY, runtime vars
7.  [MAGIC %md]  Read Data from Source Tables
8.  [python]     IS_UNIT_TEST guard → bridge global_temp or spark.table() → createOrReplaceTempView()  [try/except]
9.  [MAGIC %md]  Transformation SQL (Column Renaming and Mapping)
10. [python]     df_final = spark.sql("""SELECT ...""")           [try/except]
11. [MAGIC %md]  Write to Target Table (Load Strategy)
12. [python]     Upsert / Append / Delete-Insert                  [try/except]
13. [MAGIC %md]  Audit Log — Write Run Status to Delta Audit Table
14. [python]     spark.createDataFrame(audit_row).write...        [try/except, non-fatal]
15. [MAGIC %md]  Notebook Exit
16. [python]     dbutils.notebook.exit() or raise Exception
```

---

## Output File Naming Convention

```
{project_abbrev}_{table_name_snake_case}_{source_layer}_to_gold.py
```

Example: `opex_operational_expense_invoice_flattened_silver_to_gold.py`

Output location: `Output/CodeGeneration/`

---

## Coding Standards Checklist

- [ ] 4-space indentation, max 120 characters per line
- [ ] No hardcoded values — all via widgets and variable block
- [ ] No `display()`, `show()`, or `count()` calls
- [ ] No UDFs — use native Spark SQL functions only
- [ ] No `SELECT *` — explicit column lists only
- [ ] Unity Catalog three-part names (`catalog.schema.table`) throughout
- [ ] All data operations in `try/except` with `status = "Failed"` on exception
- [ ] Status guard: `if status == "Success" and error_message is None:`
- [ ] Audit failure is non-fatal — wrapped in its own `try/except` with `print` only
- [ ] Hyphenated catalog names wrapped in backticks in all table reference strings (e.g. `` `my-catalog`.schema.table ``)
- [ ] `spark.createDataFrame(audit_row, schema)` always called with explicit DDL schema string — never schema-inferred
- [ ] Grouped imports: stdlib → pyspark (no PepsiCo framework imports)
- [ ] SQL injected via `.format()` not f-strings inside triple-quoted SQL
- [ ] Notebook header fully populated from STTM

---

## Evals

Test cases live in `evals/evals.json`. Read that file when:
- Verifying output quality after a generation run
- Checking if a new STTM pattern is covered by existing tests
- Adding a new test case after encountering an edge case

### Eval Schema

```json
{
  "skill_name": "notebook-creation-generic",
  "evals": [
    {
      "id": 1,
      "prompt": "User task prompt exactly as typed",
      "expected_output": "Human-readable description of a passing output",
      "assertions": [
        { "text": "Specific, objectively verifiable check", "type": "content_check|file_exists|negative_check" }
      ],
      "files": ["path/to/input/sttm.csv"]
    }
  ]
}
```
