---
name: codereviewtiger
description: >
  UNIFIED CODE REVIEW SKILL — Performs a comprehensive code review of ANY Databricks notebook
  against Tiger coding standards + Generic notebook standards + 5 enhanced review categories.
  Auto-detects notebook type (Tiger Framework OR Generic) and applies the correct rule set.
  Produces a severity-ranked CSV report with a compliance score (0-100).
  USE FOR: tiger code review, codereviewtiger, review notebook, check notebook, tiger review,
  validate notebook, notebook compliance, standards check, review my notebook, full review,
  generic code review, review generic notebook, code review generic, check generic notebook,
  validate generic notebook, generic review, unified review, notebook audit, comprehensive review,
  etl review, databricks review, review code, check code, validate code.
---

# Skill: codereviewtiger — Unified Notebook Code Review

## Activation Keywords
`codereviewtiger`, `tiger code review`, `review notebook`, `check notebook`, `tiger review`,
`validate notebook`, `notebook compliance`, `standards check`, `review my notebook`, `full review`,
`generic code review`, `review generic notebook`, `code review generic`, `check generic notebook`,
`validate generic notebook`, `generic review`, `unified review`, `notebook audit`,
`comprehensive review`, `etl review`, `databricks review`, `review code`, `check code`

## Purpose
This skill is the **single entry point for all Databricks notebook code reviews** in the Tiger
Data Engineering workspace. It:

1. **Auto-detects** whether the notebook is a **Tiger Framework** notebook or a **Generic** notebook
2. **Applies the correct rule set** — Tiger standards OR Generic standards — zero false positives
3. **Extends** the base `code-review-generic` checklist with **5 additional enhanced categories**:
   Delta Table & Schema Management, Data Quality & Row Validation, Unity Catalog Compliance,
   Observability & Debug Hygiene, and Cell Structure & Magic Commands
4. **Scores** the notebook on a **0–100 compliance scale**
5. **Outputs** a severity-ranked CSV report with actionable before/after fix suggestions

## Input Requirements
1. **Notebook Path(s)**: Absolute or workspace-relative path to one or more `.py` Databricks notebooks
2. **Review Scope** (Optional): `"security only"` | `"audit only"` | `"performance"` | `"all"` (default)

## Output Location
`Output/CodeReview/{NotebookName}_TigerCodeReview_v{n}_{YYYYMMDD_HHMMSS}.csv`

---

## Workflow

### Phase 0: Auto-Detect Notebook Type

Scan the notebook and score it against type signals **before** any analysis begins.

**Tiger Framework signals** (score +1 each):
- Contains `log_audit_data(`
- Contains `%run`
- Contains `cdo_dq_framework` or `cdo_audit`
- Contains `dbutils.widgets.text("env"`
- Contains `PL_Name` widget
- Contains `audit_parameter_standard`
- Contains `NoteBookAuditLog_CL`

**Generic signals** (score +1 each):
- Contains `AUDIT_TABLE` variable declaration
- Contains `spark.createDataFrame(audit_row`
- Contains `LOAD_STRATEGY =`
- Contains `INPUT_TABLES =`
- Contains `clusterAllTags`
- Does NOT contain `log_audit_data(`
- Does NOT contain `%run`
- Does NOT contain `cdo_dq_framework`

**Decision**:
- Tiger score >= 3  → **Tiger Framework path** (Phases 1T → 2T → 2E → 3–6)
- Generic score >= 3 → **Generic path** (Phases 1G → 2G → 2E → 3–6)
- Both scores >= 2   → Ambiguous — use Tiger path, flag uncertainty in summary
- Neither >= 2       → Ask the user to confirm notebook type before proceeding

Report detected type in Phase 6: `"Notebook Type: Tiger Framework (confidence: N/7)"` or `"Generic (confidence: N/8)"`.

---

## TIGER FRAMEWORK PATH

### Phase 1T: Tiger Initialization

Load `ReviewChecklist.md` and `tigerstandards.txt`. Initialize review tracking for:
- Notebook Structure & Naming
- Header Block Completeness
- Audit Framework (log_audit_data)        ⚠️ CRITICAL
- Data Quality (DQ) Framework
- Mandatory Parameters
- Code Quality & Standards
- Security Best Practices                  ⚠️ CRITICAL
- Unity Catalog & Data Handling
- Error Handling
- Naming Conventions
- Delta Table & Schema Management          (Enhanced)
- Data Quality & Row Validation            (Enhanced)
- Unity Catalog Compliance (Extended)      (Enhanced)
- Observability & Debug Hygiene            (Enhanced)
- Cell Structure & Magic Commands          (Enhanced)

---

### Phase 2T: Tiger Code Analysis

#### T-2.1 Notebook Structure & Naming
- ✅ Notebook file named: `NB_<Sector>_<Functionality>_<Purpose>.py`
- ✅ Folder structure: `/Project/Sector/Market/`
- ❌ HIGH: Notebook name does not follow `NB_<Sector>_<Functionality>_<Purpose>` convention
- ❌ HIGH: File placed outside the `/Project/Sector/Market/` hierarchy

#### T-2.2 Header Block Completeness
- ✅ High-level description with module purpose, table names, silver database
- ✅ `Original Creator` and `Creation Date` present
- ✅ Serial change history with ADO Story/Bug references and dates
- ✅ `Gold Table Names Loaded` list
- ✅ `Source and Targets` section
- ✅ `Merge Criteria` (Upsert / SCD / Append / Delete-Insert)
- ✅ `SystemId` and `ReportingID` information
- ✅ STTM Links
- ❌ MEDIUM: Missing or incomplete header block
- ❌ LOW: Missing STTM Links
- ❌ MEDIUM: `[TO BE UPDATED]` or placeholder text left in production
- ❌ MEDIUM: Hardcoded `SystemId` or `ReportingUnitId` in header or queries

#### T-2.3 Audit Framework  ⚠️
- ✅ `log_audit_data()` called at start (Status: `"I"`)
- ✅ `log_audit_data()` called at success (Status: `"S"`) with record count
- ✅ `log_audit_data()` called on failure (Status: `"F"`)
- ✅ Errors logged to `NoteBookAuditLog_CL` via audit common module
- ❌ CRITICAL: Missing `log_audit_data()` call — notebook has no audit trail
- ❌ CRITICAL: `log_audit_data()` not called on failure path
- ❌ HIGH: Success call missing record count
- ❌ HIGH: Exceptions not propagated to the calling orchestration layer after audit log

#### T-2.4 Data Quality (DQ) Framework
- ✅ `product_name = 'CTX'` set correctly
- ✅ `SectorName` is one of: `PBNA`, `PFNA`, `LATAM`, `Europe`, `AMESA`, `APAC`
- ✅ `MarketName` uses full description (not a 2-character country code)
- ✅ Preload DQ flag checks for blocking rules
- ✅ `DataAsset` naming: `<Program>_<Market>_<BLK/TRNS/RECN>_<Table/KPI>`
- ❌ HIGH: DQ framework not implemented
- ❌ HIGH: `SectorName` uses an invalid or unsupported value
- ❌ HIGH: `MarketName` is a 2-character country code instead of full description
- ❌ MEDIUM: `DataAsset` name does not follow convention

#### T-2.5 Mandatory Parameters
- ✅ All 22 mandatory parameters present:
  `PL_Name`, `env`, `nb_path`, `no_of_periods_to_load`,
  `source_catalog_name`, `source_schema_name`, `source_table_name`, `product_name`,
  `SectorName`, `MarketName`, `dq_subject_area`, `dq_category`, `dq_subcategory`,
  `dq_dataset_layer`, `dq_dataset_name`, `dq_blocking_dataset_name`, `dq_dataset_unique_keys`,
  `target_catalog_name`, `target_schema_name`, `target_table_name`, `type_of_load`, `dq_flag`
- ✅ No hardcoded values replacing parameters
- ✅ No unused declared parameters
- ❌ HIGH: One or more mandatory parameters missing
- ❌ MEDIUM: Hardcoded value used instead of a parameter
- ❌ MEDIUM: Declared parameter never used in the notebook body

#### T-2.6 Code Quality & Standards
- ❌ CRITICAL: `display()`, `show()`, or `count()` in production code
- ❌ HIGH: `print()` statements instead of `logging.info()` / `logging.debug()`
- ❌ HIGH: Missing docstrings for functions/classes
- ❌ MEDIUM: Lines exceeding 120 characters
- ❌ MEDIUM: Methods exceeding 200 lines
- ❌ MEDIUM: Files exceeding 500 lines (excluding machine-generated code)
- ❌ MEDIUM: Functions with more than 5 parameters
- ❌ MEDIUM: Missing PEP8 compliance (indentation, spacing)
- ❌ MEDIUM: Unused imports, variables, or code sections
- ❌ MEDIUM: SQL statements not assigned to variables before `spark.sql()`
- ❌ LOW: Single-letter variable names (outside loops)

#### T-2.7 Security Best Practices  ⚠️

**Credential Management:**
- ❌ CRITICAL: Hardcoded passwords, API keys, or connection strings
- ❌ CRITICAL: Not using `dbutils.secrets.get()` for sensitive values
- ❌ HIGH: Secrets in comments or docstrings
- ❌ MEDIUM: Base64-encoded strings hiding credentials

**Secrets in Output:**
- ❌ CRITICAL: Secrets in `logging` or `print` statements
- ❌ HIGH: Connection strings exposed in exception messages

**SQL Injection:**
- ❌ CRITICAL: f-strings with external inputs inside `spark.sql()`
- ❌ HIGH: Unvalidated widget inputs used in queries
- ❌ HIGH: Missing whitelist validation for dynamic SQL

**PII / Sensitive Data:**
- ❌ CRITICAL: PII in logs without masking or hashing
- ❌ HIGH: Missing data classification tags for PII tables

**Dynamic Code Execution:**
- ❌ CRITICAL: `eval()` or `exec()` present
- ❌ HIGH: `pickle.loads()` on untrusted data

**Data Access Control:**
- ❌ CRITICAL: Direct file path access bypassing Unity Catalog ACLs
- ❌ HIGH: `USE CATALOG` / `USE SCHEMA` commands (governance bypass)
- ❌ CRITICAL: Missing three-part naming (`catalog.schema.table`)

**Network & Token Security:**
- ❌ HIGH: JDBC connections without `encrypt=true` or `ssl=true`
- ❌ HIGH: HTTP instead of HTTPS for external APIs
- ❌ HIGH: Hardcoded Azure SAS tokens or OAuth tokens
- ❌ MEDIUM: `%pip install` from untrusted repos

**Input Validation:**
- ❌ HIGH: Missing whitelist validation for all widget inputs
- ❌ HIGH: No path traversal prevention on user-supplied file paths

#### T-2.8 Error Handling
- ✅ `try/except` blocks present in all data operation sections
- ✅ Exceptions caught and logged to `NoteBookAuditLog_CL`
- ✅ Exceptions propagated to the calling orchestration layer
- ❌ CRITICAL: Missing `try/except` in a critical data load section
- ❌ HIGH: Exception caught but not logged or re-raised
- ❌ MEDIUM: Silent `except: pass` blocks swallowing errors

#### T-2.9 Unity Catalog & Data Handling
- ✅ All tables use three-part Unity Catalog names: `catalog.schema.table`
- ✅ No `hive_metastore` references
- ✅ No `USE CATALOG` / `USE SCHEMA` / `USE DATABASE` statements
- ✅ Data partitioning applied for datasets > 1 GB
- ❌ CRITICAL: `hive_metastore` catalog reference detected
- ❌ CRITICAL: Two-part table name used — Unity Catalog requires three-part
- ❌ HIGH: `USE DATABASE` / `USE CATALOG` bypasses Unity Catalog governance
- ❌ HIGH: Large dataset (> 1 GB) with no partitioning strategy

#### T-2.10 Naming Conventions
- ✅ Functions: `lowercase_with_underscores`
- ✅ Variables: `lowercase_with_underscores`
- ✅ Classes: `PascalCase`
- ✅ Constants: `UPPERCASE_WITH_UNDERSCORES`
- ✅ Meaningful, descriptive names throughout
- ❌ MEDIUM: Function names not in `snake_case`
- ❌ MEDIUM: Constants not in `UPPER_CASE`
- ❌ MEDIUM: Non-meaningful variable names (e.g. `df`, `t`, `d`)

---

## GENERIC NOTEBOOK PATH

### Phase 1G: Generic Initialization

Initialize review tracking for the 16 Generic categories below plus the 5 enhanced categories (Phase 2E).

---

### Phase 2G: Generic Code Analysis

#### 2G.1 Header & Documentation

| # | Check | Severity | Pass Condition |
|---|-------|----------|---------------|
| 1.1 | Header cell type | MEDIUM | First cell is `%md`, not a Python comment block |
| 1.2 | `## Notebook Name:` present | MEDIUM | Header contains label with actual notebook name |
| 1.3 | Purpose line | MEDIUM | `### Purpose:` or equivalent description present |
| 1.4 | Source and Target Info | MEDIUM | Table or section listing source table(s), target table, load strategy |
| 1.5 | Creator | LOW | `### Original Creator:` present and not `[TO BE UPDATED]` in production |
| 1.6 | Date Created | LOW | `### Date Created:` present |
| 1.7 | No placeholder text | LOW | No `[TO BE UPDATED]` or `<placeholder>` in production notebooks |

#### 2G.2 Imports & Framework Independence

| # | Check | Severity | Pass Condition |
|---|-------|----------|---------------|
| 2.1 | No `%run` cells | **CRITICAL** | Zero `%run` cells anywhere in notebook |
| 2.2 | No PepsiCo framework imports | **CRITICAL** | No `cdo_audit_framework_wd_la`, `cdo_dq_framework`, `audit_common`, `log_audit_data` imports |
| 2.3 | Allowed imports only | HIGH | Only `json`, `datetime`, `DeltaTable`, `pyspark.sql.*` |
| 2.4 | No Pandas import | HIGH | `import pandas as pd` absent |
| 2.5 | No `from pyspark.sql.functions import *` | MEDIUM | Explicit named imports only |
| 2.6 | No unused imports | MEDIUM | Every imported name used in notebook |

#### 2G.3 Widget Parameters

| # | Check | Severity | Pass Condition |
|---|-------|----------|---------------|
| 3.1 | Exactly 4 widgets | HIGH | `dbutils.widgets.text()` called exactly 4 times: `job_id`, `run_id`, `pipeline_name`, `run_ts` |
| 3.2 | `or`-fallback on all gets | HIGH | Every `dbutils.widgets.get("x")` assigned with `or "<fallback>"` |
| 3.3 | No `removeAll()` at top | MEDIUM | `dbutils.widgets.removeAll()` absent from top of notebook |
| 3.4 | No extra undocumented widgets | MEDIUM | No additional widgets beyond the 4 standard ones |
| 3.5 | Fallback values reasonable | LOW | `run_ts` fallback uses `datetime.utcnow()`, `job_id` fallback is `"manual_job"` |

#### 2G.4 Environment Detection

| # | Check | Severity | Pass Condition |
|---|-------|----------|---------------|
| 4.1 | Uses `clusterAllTags` | HIGH | `spark.conf.get("spark.databricks.clusterUsageTags.clusterAllTags", "")` present |
| 4.2 | Wrapped in `try/except` | HIGH | `clusterAllTags` read inside a `try:` block |
| 4.3 | `except` sets safe fallback | HIGH | `except Exception:` block sets `environment = "dev"` |
| 4.4 | No `clusterName` + `next()` pattern | HIGH | `clusterName` key not used with `next()` — fails on serverless clusters |
| 4.5 | No top-level hardcoded environment | MEDIUM | `environment = "dev"` does not appear as top-level assignment outside `except` |

#### 2G.5 Variable Block

| # | Check | Severity | Pass Condition |
|---|-------|----------|---------------|
| 5.1 | `target_tbl` declared | HIGH | `target_tbl = "..."` present as snake_case string |
| 5.2 | `AUDIT_TABLE` declared | HIGH | `AUDIT_TABLE = "..."` present with full three-part path |
| 5.3 | `INPUT_TABLES` declared | HIGH | `INPUT_TABLES = [...]` present as list |
| 5.4 | `GOLD_DB` declared | HIGH | `GOLD_DB = "..."` present as `"catalog.schema"` string |
| 5.5 | `MERGE_KEYS` declared | HIGH | `MERGE_KEYS = [...]` present as list |
| 5.6 | `LOAD_STRATEGY` declared | HIGH | `LOAD_STRATEGY = "upsert"` or `"append"` or `"delete-insert"` |
| 5.7 | Upsert requires keys | HIGH | If `LOAD_STRATEGY = "upsert"`, `MERGE_KEYS` must not be `[]` |
| 5.8 | Delete-insert has no keys | MEDIUM | If `LOAD_STRATEGY = "delete-insert"`, `MERGE_KEYS` should be `[]` |
| 5.9 | `full_target` assembled | MEDIUM | `full_target` built as `f"{GOLD_DB}.{target_tbl}"` |
| 5.10 | `status` and `error_message` initialised | HIGH | `status = "Success"` and `error_message = None` declared before first `try` block |

#### 2G.6 Catalog Name Safety  ⚠️

| # | Check | Severity | Pass Condition |
|---|-------|----------|---------------|
| 6.1 | `INPUT_TABLES` backtick-wrapped | **CRITICAL** | Any hyphenated catalog name in `INPUT_TABLES` is backtick-wrapped: `` "`my-catalog`.schema.table" `` |
| 6.2 | `GOLD_DB` backtick-wrapped | **CRITICAL** | Hyphenated catalog name in `GOLD_DB` is backtick-wrapped |
| 6.3 | `AUDIT_TABLE` backtick-wrapped | **CRITICAL** | Hyphenated catalog name in `AUDIT_TABLE` is backtick-wrapped |
| 6.4 | `full_target` string safe | HIGH | If `full_target` assembled from `GOLD_DB`, backtick already in `GOLD_DB` |
| 6.5 | Consistent wrapping | HIGH | All table references consistently backtick-wrapped or all non-hyphenated (no mix) |

> **Rule**: Catalog names containing `-` (hyphens) are not valid SQL identifiers without backtick quoting.
> Correct: `` "`my-catalog`.agentic_gold.dim_product" ``
> Wrong: `"my-catalog.agentic_gold.dim_product"` — causes SQL `ParseException` at runtime.

#### 2G.7 Source Read Pattern

| # | Check | Severity | Pass Condition |
|---|-------|----------|---------------|
| 7.1 | Uses `spark.table()` | HIGH | `spark.table(tbl)` used, not `spark.read.table(tbl)` |
| 7.2 | `createOrReplaceTempView` called | HIGH | Result registered as temp view for SQL use |
| 7.3 | Alias derived from table name | MEDIUM | Alias = `tbl.split(".")[-1]` or equivalent (last segment) |
| 7.4 | Loop over `INPUT_TABLES` | MEDIUM | Single loop handles all source tables |
| 7.5 | Read wrapped in `try/except` | HIGH | Entire read block in `try:` with `status = "Failed"` on exception |
| 7.6 | Status guard before read | HIGH | `if status == "Success" and error_message is None:` gates the read block |

#### 2G.8 Transformation SQL

| # | Check | Severity | Pass Condition |
|---|-------|----------|---------------|
| 8.1 | No f-strings in SQL | HIGH | SQL string uses `.format(...)` for injection, not f-strings |
| 8.2 | No `SELECT *` | HIGH | All columns explicitly named in SELECT |
| 8.3 | Columns aliased with `AS` | MEDIUM | Every selected column has an explicit `AS <TargetColumn>` alias |
| 8.4 | `CAST` applied for type mismatches | MEDIUM | Source type differs from target → `CAST(col AS TargetType)` present |
| 8.5 | XTN audit columns present | MEDIUM | SELECT includes `XTNCreatedTime`, `XTNCreatedById`, `XTNUpdatedTime`, `XTNUpdatedById` |
| 8.6 | SQL keywords capitalised | LOW | `SELECT`, `FROM`, `WHERE`, `JOIN`, `CAST`, `AS`, `CASE`, `WHEN` all uppercase |
| 8.7 | Triple-quoted SQL | LOW | SQL passed as `spark.sql("""...""")` not single-line string |
| 8.8 | Transform wrapped in `try/except` | HIGH | Transformation block in `try:` with `status = "Failed"` on exception |
| 8.9 | Status guard before transform | HIGH | `if status == "Success" and error_message is None:` gates the transform block |

#### 2G.9 Write Strategy (Load Strategy)

| # | Check | Severity | Pass Condition |
|---|-------|----------|---------------|
| 9.1 | Strategy matches `LOAD_STRATEGY` | HIGH | Write logic corresponds to the declared strategy |
| 9.2 | Upsert uses DeltaTable.merge | HIGH | `DeltaTable.forName(...).merge(...).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()` |
| 9.3 | Append uses write.mode("append") | HIGH | `df_final.write.format("delta").mode("append").saveAsTable(...)` |
| 9.4 | Delete-Insert uses TRUNCATE | HIGH | `spark.sql(f"TRUNCATE TABLE {full_target}")` followed by append write |
| 9.5 | No DELETE WHERE for delete-insert | HIGH | `DELETE FROM ... WHERE ...` is NOT used for delete-insert pattern |
| 9.6 | No overwrite mode | MEDIUM | `.mode("overwrite")` absent — use append after TRUNCATE |
| 9.7 | `rows_written` captured | MEDIUM | Record count captured from DeltaTable history or equivalent after write |
| 9.8 | Write wrapped in `try/except` | HIGH | Write block in `try:` with `status = "Failed"` on exception |
| 9.9 | Status guard before write | HIGH | `if status == "Success" and error_message is None:` gates the write block |

#### 2G.10 Status Guard & Error Handling

| # | Check | Severity | Pass Condition |
|---|-------|----------|---------------|
| 10.1 | `status` initialised | HIGH | `status = "Success"` before first operation |
| 10.2 | `error_message` initialised | HIGH | `error_message = None` before first operation |
| 10.3 | Read gated by status guard | HIGH | `if status == "Success" and error_message is None:` before read block |
| 10.4 | Transform gated by status guard | HIGH | `if status == "Success" and error_message is None:` before transform block |
| 10.5 | Write gated by status guard | HIGH | `if status == "Success" and error_message is None:` before write block |
| 10.6 | Exception captured to `error_message` | HIGH | Each `except` block: `error_message = str(e)` |
| 10.7 | `start_time` and `end_time` captured | MEDIUM | Timestamps captured for audit row |

#### 2G.11 Generic Audit Implementation  ⚠️

| # | Check | Severity | Pass Condition |
|---|-------|----------|---------------|
| 11.1 | `AUDIT_TABLE` used as write target | HIGH | Audit written to `AUDIT_TABLE` variable, not a hardcoded string |
| 11.2 | `audit_row` is a list of one dict | MEDIUM | `audit_row = [{...}]` structure |
| 11.3 | `rows_written` cast to `int` | HIGH | `"rows_written": int(rows_written)` in audit dict |
| 11.4 | `job_id` cast to `str` | HIGH | `"job_id": str(job_id)` in audit dict |
| 11.5 | `status` cast to `str` | HIGH | `"status": str(status)` in audit dict |
| 11.6 | Explicit DDL schema passed | **CRITICAL** | `spark.createDataFrame(audit_row, schema)` — schema is a DDL string like `"col1 STRING, col2 INT, ..."` |
| 11.7 | Schema covers all audit fields | HIGH | DDL schema string covers all fields in `audit_row` dict with correct types |
| 11.8 | Audit append mode | HIGH | `.mode("append")` used for audit write, not `"overwrite"` |
| 11.9 | Audit `try/except` non-fatal | **CRITICAL** | Audit except block uses `print("WARNING: ...")` only — does NOT set `status = "Failed"` or raise |
| 11.10 | Audit wrapped in `try/except` | HIGH | Audit write inside `try:` block |

#### 2G.12 Notebook Exit

| # | Check | Severity | Pass Condition |
|---|-------|----------|---------------|
| 12.1 | `exit_payload` is JSON | HIGH | `json.dumps({...})` used to build exit payload |
| 12.2 | Exit payload includes required fields | MEDIUM | `status`, `target_table`, `rows_written`, `error_message` in payload |
| 12.3 | Success path calls `dbutils.notebook.exit` | HIGH | `dbutils.notebook.exit(exit_payload)` on success |
| 12.4 | Failure path raises Exception | HIGH | `raise Exception(error_message)` on failure |
| 12.5 | Exit not unconditional | HIGH | `dbutils.notebook.exit()` not called before the success/failure branch |

#### 2G.13 Code Quality & Standards

| # | Check | Severity | Pass Condition |
|---|-------|----------|---------------|
| 13.1 | No `display()` or `show()` | MEDIUM | Both absent from production code |
| 13.2 | No standalone `count()` | MEDIUM | `.count()` absent unless captured in `rows_written` |
| 13.3 | Line length ≤ 120 characters | MEDIUM | No line exceeds 120 characters |
| 13.4 | 4-space indentation | MEDIUM | No tabs; consistent 4-space indentation |
| 13.5 | No hardcoded table names outside variable block | MEDIUM | Table names only in `INPUT_TABLES`, `GOLD_DB`, `AUDIT_TABLE` |
| 13.6 | Descriptive variable names | MEDIUM | No single-letter names outside loop counters and `except e` |

#### 2G.14 Security Best Practices  ⚠️

| # | Check | Severity | Pass Condition |
|---|-------|----------|---------------|
| 15.1 | No hardcoded credentials | **CRITICAL** | No passwords, tokens, API keys, connection strings in code |
| 15.2 | No SQL injection via f-strings | **CRITICAL** | Widget values not concatenated into `spark.sql()` via f-strings |
| 15.3 | No `eval()` or `exec()` | **CRITICAL** | Neither present in notebook |
| 15.4 | No secrets in print/log | **CRITICAL** | `print()` and logging do not output credential values |
| 15.5 | Widget input validated | HIGH | Widget inputs used in SQL wrapped with `.format()` named placeholders |
| 15.6 | No PII in logs | HIGH | PII columns masked/hashed before logging |
| 15.7 | JDBC encrypted | HIGH | JDBC connection strings include `encrypt=true` |
| 15.8 | HTTPS only | HIGH | No HTTP for external API calls |
| 15.9 | Trusted `%pip install` only | MEDIUM | Package installs from approved registries only |
| 15.10 | No Base64-encoded credentials | MEDIUM | No `base64.b64decode(...)` used to retrieve secrets |

#### 2G.15 Naming Conventions
- ✅ Variable names in `snake_case` (e.g. `target_tbl`, `rows_written`)
- ✅ Constants in `UPPER_CASE_WITH_UNDERSCORES` (e.g. `AUDIT_TABLE`, `MERGE_KEYS`)
- ✅ Standard variable names: `GOLD_DB`, `AUDIT_TABLE`, `INPUT_TABLES`, `MERGE_KEYS`, `LOAD_STRATEGY`, `target_tbl`
- ❌ MEDIUM: Constants declared in `snake_case` instead of `UPPER_CASE`
- ❌ MEDIUM: Non-descriptive variable names (e.g. `df`, `tbl1`, `t`)
- ❌ LOW: SQL temp view alias not matching last segment of table name

---

## SHARED ENHANCED CHECKS (Both Tiger and Generic Paths)

These 5 enhanced sections apply to **both** Tiger Framework and Generic notebooks.
Execute them after the path-specific checks above.

### Phase 2E: Enhanced Review Categories

#### 2E.1 Delta Table & Schema Management  ⚠️
- ✅ `DeltaTable.forName(spark, full_target)` used (not deprecated `DeltaTable.forPath()`)
- ✅ No `.option("mergeSchema", "true")` without an inline justification comment
- ✅ No `.option("overwriteSchema", "true")` on Gold writes
- ✅ No `.mode("overwrite")` on a partitioned Gold table without `replaceWhere`
- ✅ DDL schema string used for `spark.createDataFrame()` (not `StructType` object)
- ❌ MEDIUM: `DeltaTable.forPath()` used — replace with `DeltaTable.forName(spark, target)`
- ❌ MEDIUM: `.option("mergeSchema", "true")` without a comment explaining schema evolution intent
- ❌ CRITICAL: `.option("overwriteSchema", "true")` on Gold write — silently drops columns
- ❌ HIGH: `.mode("overwrite")` on partitioned Gold table without `replaceWhere` — full overwrite risk
- ❌ MEDIUM: MERGE condition references columns not in declared merge keys without justification

#### 2E.2 Data Quality & Row Validation
- ✅ Null check on all merge key columns before upsert (e.g. `df_final.filter(col("key").isNotNull())`)
- ✅ Deduplication guard before upsert (`.dropDuplicates(keys)`)
- ✅ Source row count validated before delete-insert (`count() > 0` before `TRUNCATE`)
- ✅ `rows_written` validated after write — warning printed on zero rows
- ✅ `rows_written` always cast to `int` — not `None`, float, or `long`
- ❌ HIGH: No null check on merge keys before upsert — nulls cause incorrect MERGE matches
- ❌ HIGH: No deduplication before upsert — duplicate source rows create double-write anomalies
- ❌ HIGH: Empty source not checked before delete-insert — TRUNCATE on empty source clears Gold table
- ❌ MEDIUM: `rows_written == 0` not validated — silent zero-row writes accepted
- ❌ HIGH: `rows_written` type is not `int` — causes schema validation failure in audit row

#### 2E.3 Unity Catalog Compliance  ⚠️
- ✅ All table references use full three-part names: `catalog.schema.table`
- ✅ No `USE DATABASE` / `USE CATALOG` / `USE SCHEMA` statements
- ✅ No `hive_metastore` catalog references
- ✅ No `dbfs:/` paths for table reads
- ✅ No `spark.catalog.setCurrentDatabase()` calls
- ❌ CRITICAL: `hive_metastore.schema.table` reference — must migrate to Unity Catalog
- ❌ CRITICAL: Two-part table name used — Unity Catalog requires three-part
- ❌ HIGH: `USE DATABASE {schema}` present — bypasses Unity Catalog governance
- ❌ HIGH: `dbfs:/user/hive/warehouse/...` path used instead of catalog table reference
- ❌ HIGH: `spark.catalog.setCurrentDatabase()` used — implicit namespace resolution not allowed
- ❌ MEDIUM: `SHOW TABLES` / `SHOW DATABASES` in production code

#### 2E.4 Observability & Debug Hygiene
- ✅ No bare `print()` in main execution path (only inside `except` blocks)
- ✅ Widget values not printed to console (prevents log exposure)
- ✅ No `display()`, `show()`, `.count()` in production code paths
- ✅ No commented-out debug code blocks
- ✅ No unresolved `# TODO` / `# DEBUG` comments
- ❌ HIGH: Widget values printed to console — log exposure risk (e.g. `print(job_id)`)
- ❌ MEDIUM: `display(df)` or `df.show()` left in production — performance overhead + data exposure
- ❌ MEDIUM: Commented-out debug blocks (`# df.show()`, `# display(df)`) left in code
- ❌ MEDIUM: `print(error_message)` in main path — exposes internal errors to output
- ❌ LOW: Unresolved `# TODO` or `# DEBUG` comments in production code

#### 2E.5 Cell Structure & Magic Commands
- ✅ Section headers use `%md` cells (not Python `# ===` banners)
- ✅ Production DML in Python cells using `spark.sql()` — not in `%sql` cells
- ✅ No `%fs` cells — file system operations belong in the orchestration layer
- ✅ No `%sh` cells — shell commands not permitted in Gold notebooks
- ✅ No `%pip install` in notebook cells — use cluster init scripts
- ❌ MEDIUM: Python `# ===` banners used as section dividers instead of `%md` cells
- ❌ HIGH: `%sql` cells used for production `INSERT`, `MERGE`, or `TRUNCATE`
- ❌ HIGH: `%fs ls` / `%fs rm` present — bypasses Unity Catalog access controls
- ❌ HIGH: `%sh pip install` present in notebook cells
- ❌ LOW: Extra debug `%md` cells inserted between operation blocks

---

### Phase 3: Criticality Assessment

**CRITICAL** (Blocking — runtime failures, security breaches, or data loss):
- Missing `log_audit_data()` calls (Tiger only)
- Hardcoded credentials, passwords, API keys, OAuth tokens
- SQL injection via f-strings with user input in `spark.sql()`
- `eval()` or `exec()` with dynamic content
- PII in logs without masking
- `hive_metastore` catalog reference (Unity Catalog violation)
- Two-part table name (`schema.table`) instead of three-part
- `.option("overwriteSchema", "true")` on Gold write
- `spark.createDataFrame(audit_row)` without explicit DDL schema (Generic only)
- Audit `except` block sets `status = "Failed"` — audit must be non-fatal (Generic only)
- Hyphenated catalog name not backtick-wrapped — SQL parse error at runtime (Generic only)
- `%run` in a Generic notebook (breaks framework independence)
- Direct file path access bypassing Unity Catalog ACLs
- Writes to unapproved external locations
- `display()`, `show()`, or `count()` in production code (Tiger only)

**HIGH** (Correctness risks — fix before merge):
- `spark.read.table()` instead of `spark.table()` (Generic)
- Missing `or`-fallback on `dbutils.widgets.get()` (Generic)
- `clusterName` + `next()` pattern instead of `clusterAllTags` (Generic)
- Missing status guard (`if status == "Success" and error_message is None:`) on any block (Generic)
- `LOAD_STRATEGY = "upsert"` with `MERGE_KEYS = []` (Generic)
- Delete-Insert using `DELETE FROM ... WHERE ...` instead of `TRUNCATE TABLE`
- No null check on merge keys before upsert
- No deduplication before upsert (double-write risk)
- Empty source not checked before delete-insert
- `rows_written` type is not `int`
- Missing mandatory Tiger parameters (Tiger only)
- `USE DATABASE` / `USE CATALOG` statements
- `%sql` / `%fs` / `%sh` cells in production
- Widget values printed to console
- `.mode("overwrite")` on partitioned Gold table without `replaceWhere`

**MEDIUM** (Code quality — fix within sprint):
- PEP8 violations (indentation, spacing, line length > 120)
- Hardcoded table names outside the variable block
- Missing `CAST(...)` for type-mismatched columns
- XTN audit columns missing from SELECT
- `rows_written` not captured after write
- `rows_written == 0` not validated
- `DeltaTable.forPath()` instead of `DeltaTable.forName()`
- `.option("mergeSchema", "true")` without justification comment
- MERGE condition not using partition columns
- Section headers using Python comments instead of `%md` cells
- Commented-out debug code blocks
- Non-descriptive variable names
- `print()` outside `except` block in main execution path
- Missing docstrings on functions/classes (Tiger only)
- SQL statements not assigned to variables (Tiger only)
- Silent `except: pass` blocks (Tiger only)

**LOW** (Documentation and style):
- Incomplete header block fields
- `[TO BE UPDATED]` placeholder text in production
- SQL keywords not capitalised
- Missing STTM Links (Tiger only)
- Unresolved `# TODO` / `# DEBUG` comments
- SQL temp view alias not matching last segment of table name

---

### Phase 4: Generate Recommendations

For each violation found, produce a recommendation entry with:

| Field | Description |
|-------|-------------|
| **Category** | Check category (e.g. `T-2.3 Audit Framework`, `2G.11 Generic Audit`, `2E.3 Unity Catalog`) |
| **Criticality** | `CRITICAL` / `HIGH` / `MEDIUM` / `LOW` |
| **Line_Number** | Exact line number(s) where the issue occurs |
| **Issue_Description** | One-sentence description of the violation |
| **Current_Code** | Problematic snippet (max 3 lines; add `...` if truncated) |
| **Suggested_Fix** | Specific corrected code |
| **Recommendation** | Explanation and reference to the checklist rule or `tigerstandards.txt` section |

---

### Phase 5: Generate CSV Report

```csv
Category,Criticality,Line_Number,Issue_Description,Current_Code,Suggested_Fix,Recommendation
```

**CSV Output Rules:**
- Sort by Criticality (CRITICAL → HIGH → MEDIUM → LOW), then by Line Number ascending
- Escape double quotes by doubling them (`""`)
- Truncate code snippets to 3 lines; append `...` if longer
- Append a summary statistics row at the bottom (total violations per criticality level)
- Filename: `{NotebookName}_TigerCodeReview_v{n}_{YYYYMMDD_HHMMSS}.csv`
- Increment `v{n}` if a previous review CSV already exists for the same notebook
- Save to: `Output/CodeReview/`

---

### Phase 6: Summary Report

After generating the CSV, print:

```
=====================================================================
  codereviewtiger — Unified Code Review Summary
  Notebook  : {NotebookName}
  Reviewed  : {YYYY-MM-DD HH:MM}
=====================================================================
  Notebook Type    : Tiger Framework (confidence: N/7)
                   | Generic (confidence: N/8)
  Review Path      : Tiger T-2.1-T-2.10 | Generic sections 1-15
                     + Enhanced 2E.1-2E.5 (both paths)

  Compliance Score : {score}/100
    Scoring method:
      Start at 100
      CRITICAL issue : -15 each  (max deduction -45)
      HIGH issue     :  -5 each  (max deduction -20)
      MEDIUM issue   :  -2 each  (max deduction -15)
      LOW issue      :  -1 each  (max deduction  -5)

  Total Issues : {count}
    CRITICAL : {n}  <- Blocking — must fix before merge
    HIGH     : {n}  <- Fix before raising PR
    MEDIUM   : {n}  <- Fix within sprint
    LOW      : {n}  <- Fix when convenient

  Category Breakdown:
    Audit Framework / Generic Audit    : {n} issues
    Security                           : {n} issues
    Unity Catalog Compliance           : {n} issues
    Delta / Schema Management          : {n} issues
    Data Quality / Row Validation      : {n} issues
    Observability & Debug Hygiene      : {n} issues
    Cell Structure & Magic Commands    : {n} issues
    Code Quality & Standards           : {n} issues
    Documentation & Header             : {n} issues
    Naming Conventions                 : {n} issues
    Parameters (Tiger only)            : {n} issues
    DQ Framework (Tiger only)          : {n} issues

  Top Issues:
    1. [Line {n}] CRITICAL - {description}
    2. [Line {n}] CRITICAL - {description}
    3. [Line {n}] HIGH     - {description}
    ...

  Recommended Next Steps:
    1. Fix all CRITICAL issues immediately (they block merge)
    2. Address HIGH issues before raising a PR
    3. Schedule MEDIUM fixes within the current sprint

  Output : Output/CodeReview/{filename}.csv

  Auto-Fix available: Reply "auto-fix CRITICAL", "auto-fix HIGH",
  or "auto-fix all" to apply safe deterministic fixes automatically.
=====================================================================
```

---

## Auto-Fix Mode

When the user replies with `"auto-fix CRITICAL"`, `"auto-fix HIGH"`, or `"auto-fix all"`, apply only **safe and deterministic** fixes:

| Fix | Applies To |
|-----|-----------|
| Wrap hyphenated catalog names in backticks | Generic |
| Add `or "<fallback>"` to every `dbutils.widgets.get()` | Generic |
| Add explicit DDL schema string to `spark.createDataFrame(audit_row)` | Generic |
| Replace `spark.read.table()` with `spark.table()` | Generic |
| Replace `DeltaTable.forPath()` with `DeltaTable.forName(spark, full_target)` | Both |
| Add null checks on merge keys before upsert | Both |
| Remove bare `print()` calls from main execution path | Both |
| Replace `%sql` DML cells with equivalent `spark.sql()` Python cells | Both |

For ambiguous or logic-altering changes (merge key values, load strategy, SQL transformation logic) — list them separately and ask the user to confirm before applying.

After auto-fix, re-run Phase 2 and 2E checks on the modified file and generate an updated CSV with the version number incremented.

---

## Implementation Notes

### Multi-File Reviews
When multiple notebooks are provided:
1. Run Phase 0 type detection independently for each file
2. Apply the correct rule set per notebook
3. Generate a separate CSV per notebook
4. Print a consolidated cross-file summary with aggregate compliance scores

### Context-Specific Exceptions
- `print("WARNING: ...")` inside Generic audit `except` blocks — **allowed** (non-fatal signal)
- `status = "Failed"` inside Read / Transform / Write `try/except` — **correct** (status-chain)
- `status = "Failed"` inside **audit** `try/except` — **violation** (audit must be non-fatal)
- Single-letter loop variables (`e` in `except Exception as e`) — **allowed**
- `.count()` used to capture `rows_written` immediately after a write — **allowed**
- `display()` inside a cell explicitly marked `# DEVELOPMENT ONLY` — flag as LOW only

### Relationship to Other Skills
This skill supersedes and combines:
- `code-review` skill (Tiger-only)
- `code-review-generic` skill (Generic-only)

---

## Error Handling
If the notebook cannot be read or parsed:
1. Log the error with file path and diagnostic detail
2. Create a CSV with a single entry:
   `"ERROR,CRITICAL,0,Unable to parse notebook file,{error detail},,Verify file encoding and confirm it is a valid Databricks .py notebook"`
3. Print diagnostic information to the user and ask them to verify the file path

---

## Success Criteria
- ✅ Notebook type auto-detected with confidence score reported
- ✅ Correct rule set applied — zero false positives from the wrong path
- ✅ All 5 enhanced categories evaluated (2E.1–2E.5)
- ✅ CSV sorted CRITICAL → LOW with line numbers and suggested fixes
- ✅ Compliance score (0–100) calculated and displayed
- ✅ Output saved to `Output/CodeReview/`
- ✅ Summary printed with top issues and recommended next steps

---

## Example Prompts

```
codereviewtiger Output/CodeGeneration/edf_dim_product_silver_to_gold.py
```
```
tiger code review Notebooks/NB_BR_Sales_LoadGold.py
```
```
review notebook Output/CodeGeneration/agentic_dim_product_silver_to_gold.py security only
```
```
validate notebook for all files in Output/CodeGeneration/
```
```
codereviewtiger Output/CodeGeneration/edf_dim_product_silver_to_gold.py
auto-fix CRITICAL
```
