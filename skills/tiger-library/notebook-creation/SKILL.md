---
name: notebook-creation
description: >-
  Generate production-ready Databricks .py notebooks for Silver-to-Gold or
  Bronze-to-Gold ETL pipelines from STTM CSV files, following PepsiCo DTV
  Global Data Engineering standards. Use this skill whenever the user mentions
  building notebooks, creating ETL code, generating Gold layer pipelines,
  silver to gold, bronze to gold, code generation, new notebook, STTM to code,
  or wants to turn an STTM into a runnable Databricks notebook — even if they
  don't explicitly say "notebook creation". Also use when the user says "build",
  "code", "generate code", "etl notebook", or asks to scaffold a Gold layer
  notebook from column mappings.
---

# Notebook Creation Skill — Databricks Notebook (.py) Generation

## Purpose
Generate a production-ready Databricks notebook `.py` file for Silver-to-Gold or Bronze-to-Gold ETL
pipelines, following PepsiCo DTV Global Data Engineering standards.
The output is derived from the reference template
`references/_project_code_abrrev__table_name___layer__to_gold.py` and populated using
the Source-to-Target Mapping (STTM) found in `Output/STTM_DDL_creation/`.

---

## Reference Files

| File | Purpose | When to Read |
|---|---|---|
| `references/_project_code_abrrev__table_name___layer__to_gold.py` | Base template — all generated notebooks extend this | Before generating any notebook |
| `Output/STTM_DDL_creation/*.csv` | Source of truth for column mappings, merge keys, system IDs | Every generation run |
| `Output/STTM_DDL_creation/*.sql` | DDL for target table structure validation | To cross-check data types |

---

## Inputs Required

Before generating, identify the following from the STTM or user request:

| Input | Source | Example |
|---|---|---|
| Project Code Abbreviation | User / STTM | `opex` |
| Target Table Name | STTM → `Target Table Name*` column | `OperationalExpenseInvoiceFlattened` |
| Gold Database Name | STTM → `Target Data Lake*` column | `uc_prod_snt_gld_01.snp_common_transactions` |
| Source Tables | STTM → `Source Schema Name` + `Source Table name` | `fdn_supplier.XTNBusinessTravelFlightReservation` |
| Merge Keys | STTM → `Merge Key` = `Yes` columns | `InvoiceSourceName`, `XTNDFSystemId`, `XTNDFReportingUnitId` |
| System ID | STTM → `XTNDFSystemId` default value | `101474` |
| Reporting Unit ID | STTM → `XTNDFReportingUnitId` default value | `107019` |
| Merge Strategy | STTM → `Merge Key` / `Primary Key` pattern | Upsert / Append / SCD2 / Delete-Insert |
| Market | User / project_params | `GLOBAL` |
| Creator Name | User or default `[TO BE UPDATED]` | `Jane Doe` |
| ADO Story / Bug ID | User or default `[TO BE UPDATED]` | `US-98765` |

---

## STTM Parsing Instructions

The STTM CSV is the single source of truth for column mappings. When a STTM CSV is provided (e.g., `Output/STTM_DDL_creation/*.csv`), extract the following:

### STTM Column Reference

| STTM Column | Notebook Location | How It's Used |
|---|---|---|
| `Source Schema Name` | Header doc + `input_tbls` | Full Unity Catalog path of source |
| `Source Table name` | Header doc + SQL FROM clause | Source table name in JOIN |
| `Column Name*` | SQL SELECT source expression | Source column (or compound expression if Derived) |
| `Data Transformation Rules*` | SQL SELECT expression | Copy verbatim as transformation; CASE WHEN → inline |
| `Target Column*` | SQL column alias (`AS`) | Gold column name |
| `Target Data Type*` | `CAST(... AS ...)` in SQL | Wraps expression in appropriate CAST |
| `Allow Nulls*` | Comments / DQ rule | `NOT NULL` → add NOT NULL DQ check |
| `Merge Key` = `Yes` | `MERGE_KEYS` list + MERGE ON | Part of the MERGE ON condition |
| `Primary Key` = `Yes` | Header documentation | Cross-reference for uniqueness |
| `Target Data Lake*` | `gold_database_name` variable | Unity Catalog `catalog.schema` prefix |
| `Target Table Name*` | `target_tbl` widget default | Gold Delta table name |
| `Default Value` | `lit(...)` or constant in SQL | Used when Source Name has no source column |
| `Source Name` = `Derived` | Derived column in SQL | Expression built from `Data Transformation Rules*` |
| `FK Table.columnname` | JOIN condition comment | Documents foreign key relationship |

### 4. System & Reporting IDs
From rows where `Target Column*` = `XTNDFSystemId` / `XTNDFReportingUnitId`, read the `Default Value` — these become `systemId` and `reportingUnitId` in `project_params`.

### 5. Merge Strategy Detection
| STTM Pattern | Merge Strategy | Write Pattern |
|---|---|---|
| `Merge Key` = `Yes` columns present | **Upsert** (MERGE INTO) | `DeltaTable.merge(...).whenMatchedUpdateAll().whenNotMatchedInsertAll()` |
| No `Merge Key`, only `Primary Key` | **Append** (INSERT INTO) | `df.write.format("delta").mode("append")` |
| `SCD` columns: `effective_date`, `end_date`, `is_current` | **SCD Type 2** | Custom SCD2 merge logic |
| Full reload pattern (`TRUNCATE` + `INSERT`) | **Delete-Insert** | `DELETE WHERE XTNDFSystemId = {id}` then append |
| No keys, incremental flag | **Append** | `df.write.format("delta").mode("append")` |

### 6. Source Joins from FK References
For each populated `FK Table.columnname` cell: generate `INNER JOIN {fk_table} ON {source}.{pk} = {fk_table}.{fk_col}`.

### 7. Filter Extraction from STTM
Check the `Comments` column: `Source filter:` → add to WHERE clause; `latest` / `ROW_NUMBER()` → add window function with PARTITION BY / ORDER BY.

### 8. Handling Derived Columns
When `Source Name = Derived`: copy `Data Transformation Rules*` verbatim as the SQL expression, then wrap with `CAST(... AS <Target Data Type*>) AS <Target Column*>`.

### 9. Common Data Type Mappings

| STTM Type | Databricks Type |
|---|---|
| `string` | `STRING` |
| `date` / `timestamp` | `DATE` / `TIMESTAMP` |
| `decimal(p,s)` | `DECIMAL(p,s)` |
| `int` / `bigint` | `INT` / `BIGINT` |
| `boolean` | `BOOLEAN` |

---

## Notebook Generation Process

### Step 1 — Parse STTM
1. Read the STTM CSV from `Output/STTM_DDL_creation/`
2. Extract sources, target, merge keys, transformations, system IDs
3. Identify merge strategy
4. Write the finished `.py` notebook to `Output/CodeGeneration/`

### Step 2 — Populate Header (Magic Markdown Cell)
Fill in the notebook header using the template format:
```
## Project Name: <Derived from target table / project abbreviation>
### Purpose: Reads from <source layer> and loads <Gold Table Name>
### Original Creator: <name or [TO BE UPDATED]>
### Date Created: <today's date>
### System ID / Reporting Unit ID: from STTM XTNDFSystemId / XTNDFReportingUnitId defaults
### Version History: ADO Story / Bug reference
### Source and Target Info: from STTM source→target mapping with merge strategy
```

### Step 3 — Imports Section
Group imports: stdlib → pyspark → pepsico frameworks. Follow pattern in `references/_project_code_abrrev__table_name___layer__to_gold.py`.

### Step 4 — Widget Parameters
Declare all 7 standard widgets (`additional_params`, `dataset_name`, `environment`, `job_id`, `project_params`, `source_layer`, `table_name`). Follow pattern in reference template.

### Step 5 — Variable Declaration
Extract `systemId`, `reportingUnitId`, `gold_database_name`, `market_name`, `input_tbls`, `dq_enable_flag`, `load_ts`, `status`, `error_message` from params. Follow pattern in reference template.

### Step 6 — Transformation SQL
Build the transformation SQL using STTM column mapping:
- For each STTM row: use `Data Transformation Rules*` as the expression
- Direct copies: `<source_col> AS <target_col>`
- CASE WHEN derived: use exact expression from STTM

Always append these **Mandatory Audit Columns** at the end of every SELECT:

| Target Column | Expression | Notes |
|---|---|---|
| `CountryIso2Code` | `lit('US')` or from STTM default | ISO 3166-1 country code |
| `XTNMarketCode` | `additional_params["market_code"]` | Market/sector identifier |
| `XTNDFSystemId` | `CAST({systemId} AS INT)` | From STTM XTNDFSystemId default value |
| `XTNDFReportingUnitId` | `CAST({reportingUnitId} AS INT)` | From STTM XTNDFReportingUnitId default value |
| `XTNCreatedTime` | `TO_TIMESTAMP('{load_ts}', 'yyyy-MM-dd HH:mm:ss.SSS')` | Insert timestamp (immutable after insert) |
| `XTNCreatedById` | `CAST(TRIM('{job_id}') AS STRING)` | Databricks job ID (immutable) |
| `XTNUpdatedTime` | `TO_TIMESTAMP('{load_ts}', 'yyyy-MM-dd HH:mm:ss.SSS')` | Refreshed on every upsert |
| `XTNUpdatedById` | `CAST(TRIM('{job_id}') AS STRING)` | Refreshed on every upsert |

### Step 7 — Merge / Write Strategy
Generate the write logic based on detected merge strategy:

#### Upsert (MERGE INTO)
```python
delta_table.alias("tgt").merge(
    df_final.alias("src"),
    " AND ".join([f"tgt.{k} = src.{k}" for k in merge_keys])
).whenMatchedUpdateAll(
).whenNotMatchedInsertAll(
).execute()
```

#### Append
```python
df_final.write.format("delta").mode("append").saveAsTable(f"{gold_database_name}.{target_tbl}")
```

#### Delete-Insert
```python
spark.sql(f"DELETE FROM {gold_database_name}.{target_tbl} WHERE XTNDFSystemId = {systemId}")
df_final.write.format("delta").mode("append").saveAsTable(f"{gold_database_name}.{target_tbl}")
```

### Step 8 — Error Handling
Wrap every data operation in `try/except`; on failure set `status = "Failed"` and call `au.log_audit_data(status_cd=status_cd_failure, ...)`. Follow pattern in reference template.

### Step 9 — Notebook Exit
Call `notebook_exit_return_parameters(...)` on success; `raise Exception(error_message)` on failure. Follow pattern in reference template.

---

## Full Notebook Structure (Section Order)

```
1.  [MAGIC %md] Header Documentation Cell
2.  [MAGIC %md] Running Utility Notebook
3.  [MAGIC %run]  ./notebook_common_utils
4.  [MAGIC %md] Running Parameter Notebook
5.  [MAGIC %run]  ./notebook_common_variables
6.  [MAGIC %md] Importing the Necessary Packages
7.  [python]    Import statements (grouped: stdlib → pyspark → pepsico frameworks)
8.  [MAGIC %md] Get values from widgets
9.  [python]    dbutils.widgets.text(...)  +  dbutils.widgets.get(...)
10. [MAGIC %md] JSON String Document into Python Dictionary
11. [python]    re.sub / json.loads for project_params and additional_params
12. [MAGIC %md] Variable declaration
13. [python]    All variable assignments (systemId, reportingUnitId, audit vars, prints)
14. [MAGIC %md] Audit Logic - Initialization
15. [python]    au.log_audit_data(status=status_cd_initial)
16. [MAGIC %md] Read Data from Foundation Layer
17. [python]    read_data_foundation_tables_udf(...) + audit log
18. [MAGIC %md] Column Renaming and Transformations
19. [python]    spark.sql("""SELECT ... FROM ...""")
20. [MAGIC %md] Validation Check for System ID and Reporting Unit ID
21. [python]    check_for_systemid_reporting_id(df_final, sys_rpt_id_config_dict)
22. [MAGIC %md] DQ Framework Implementation
23. [python]    dqm_framework.dq_framework_invoke(...)  [if dq_enable_flag]
24. [MAGIC %md] Write to the Gold Zone
25. [python]    MERGE / Append / Delete-Insert logic + audit log
26. [MAGIC %md] Capture Statistics
27. [python]    get_statistics_of_data_loaded(...)
28. [MAGIC %md] Notebook Exit Parameters
29. [python]    notebook_exit_return_parameters(...) or raise Exception
```

---

## Output File Naming Convention

```
snp_{table_name_snake_case}_{source_layer}_to_gold.py
```

Example: `snp_costed_bom_silver_to_gold.py` → `Output/CodeGeneration/`

---

## Coding Standards Checklist

- [ ] 4-space indentation, max 120 chars per line
- [ ] No hardcoded values — all via JSON widgets
- [ ] No `display()`, `show()`, or `count()`
- [ ] No UDFs — use native Spark functions
- [ ] No `SELECT *` — explicit column lists only
- [ ] `select()` instead of chained `withColumn()`
- [ ] Unity Catalog three-part names (`catalog.schema.table`)
- [ ] All data ops in `try/except` with `au.log_audit_data()` on failure
- [ ] Status guard: `if status == "Success" and error_message is None:`
- [ ] Grouped imports: stdlib → pyspark → pepsico
- [ ] Notebook header fully populated

---

## Evals

Test cases for this skill live in `evals/evals.json`. Read that file when:
- Verifying output quality after a generation run
- Checking whether a new STTM pattern is covered by existing tests
- Adding a new test case after encountering an edge case

### Eval Schema (per Anthropic skill-creator spec)

```json
{
  "skill_name": "notebook-creation",
  "evals": [
    {
      "id": 1,
      "prompt": "User's task prompt exactly as typed",
      "expected_output": "Human-readable description of what a passing output looks like",
      "assertions": [
        { "text": "Specific, objectively verifiable check on the output file", "type": "content_check|file_exists|negative_check" }
      ],
      "files": ["path/to/input/sttm.csv"]
    }
  ]
}
```

### Current Eval Coverage (`evals/evals.json`)

| ID | Scenario | Merge Strategy | Key Assertions |
|---|---|---|---|
| 1 | Full STTM with 29 columns, Upsert | Upsert (MERGE INTO) | File exists, header present, no hardcoded IDs, audit calls, no `show()` |
| 2 | No merge keys → Append strategy | Append | `.mode('append')` not MERGE INTO, 29-section structure preserved |
| 3 | SCD Type 2 columns in STTM | SCD2 | Expiry logic, `is_current`, effective/end dates, Unity Catalog naming |

### Adding a New Eval

Add to `evals/evals.json` following the schema above. Good test prompts are:
- Realistic — the kind a data engineer would actually type
- Specific — include table names, source paths, or STTM column patterns
- Discriminating — would fail if the skill regresses on merge strategy detection or audit columns


