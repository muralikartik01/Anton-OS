# DRD/DAT Gap Assessment — Detailed Workflow

This document contains the full step-by-step processing logic for the drd-dat-gap-assessment skill.
Only the `drd-dat-assessor` agent should reference this workflow.

---

## Step 1 — Resolve and Convert Input Files

### 1a — Resolve Excel Files From Manifest
Read `specs/{use_case}/manifest.md` and resolve only:

- `DRD Excel`
- `DAT Excel`

Do not scan the repo for alternate Excel files when the manifest provides concrete paths.

### 1b — Resolve Python Command
Before invoking the converter:

1. call `configure_python_environment`
2. call `get_python_executable_details`
3. use the returned command prefix as `<resolved_python>`

### 1c — Convert Excel to CSV
Run `excel_to_csv_converter.py` from `harness/skills/excel-to-csv/references/` against each workbook.
Use **separate output subdirectories** per file to prevent sheet name collisions:

```bash
<resolved_python> harness/skills/excel-to-csv/references/excel_to_csv_converter.py \
   --input "<DRD_filename.xlsx>" \
   --output "harness/specs/{use_case}/csv/DRD"

<resolved_python> harness/skills/excel-to-csv/references/excel_to_csv_converter.py \
   --input "<DAT_filename.xlsx>" \
   --output "harness/specs/{use_case}/csv/DAT"
```

The converter removes columns that are blank across the header row and all retained data rows before writing CSV.

### 1d — Identify Relevant Sheet CSVs
- `harness/specs/{use_case}/csv/DRD/` — find main DRD sheet (commonly `Data_Requirements_DRD.csv`)
- `harness/specs/{use_case}/csv/DAT/` — find subject area sheets (largest non-instruction sheet)
- `harness/specs/{use_case}/csv/DAT/Data_Dictionary.csv` — use when present as an advisory enrichment source for PK/FK and data type inference

### 1e — Read CSV Files
Use `read_file` tool to read first 20-30 lines of each relevant CSV:
1. Identify the header row (usually row 2-4 after metadata)
2. Inspect column structure
3. Count data rows
4. If `Data_Dictionary.csv` exists, identify its business header row before parsing recommendations

---

## Step 2 — Validation Logic (In-Memory Processing)

### Column Validation
1. Read CSV using `read_file` tool
2. Parse header row (identify row with "Data Product Requirement", "Subject Area Name", etc.)
3. Extract column names by splitting header row on commas
4. Compare against expected mandatory columns (case-insensitive substring matching)
5. Store missing columns

### Data Extraction
1. Parse each data row (rows after header)
2. Split by comma, handle quoted fields
3. Build in-memory data structures:
   - DRD: List of dicts with keys: drd_attribute, drd_description, drd_example, drd_dq_expectations
   - DAT: List of dicts with keys: dat_physical_attr, dat_logical_name, dat_from_drd, dat_table, dat_gap, dat_gap_desc, dat_business_def, dat_scenario
   - Data Dictionary: List of dicts with keys: dict_attr, dict_table, dict_data_type, dict_length, dict_scale, dict_pkfk, dict_nullability

### Mandatory Column Fill-Value Check
For DRD 8 mandatory columns and DAT 7 mandatory columns:
- Column must exist in the header row
- ≥80% of data rows must have non-blank values in that column
- If column exists but <80% filled → flag as `⚠️ UNDERFILLED`
- If column missing entirely → flag as `❌ MISSING`

### Data Dictionary Enrichment
If `harness/specs/{use_case}/csv/DAT/Data_Dictionary.csv` exists:
1. Identify the header row containing `Field Name / Attribute Name (Technical)` and `Data Type`
2. Parse each data row into normalized values for attribute name, source/table name, PK/FK flag, data type, length, scale, and nullability
3. Match each DAT row case-insensitively on `Physical Attribute Name`; use `Physical(Technical) Table Name` as a tiebreaker when `Source / Table Name` is populated in the data dictionary
4. Use matched rows to infer advisory `Primary Key / Foreign Key` and a rendered source data type string derived from `Data Type`, `Length`, and `Scale`
5. If multiple rows match or no confident match is available, emit `NOT INFERRED`
6. If the sheet is absent, record `Data Dictionary not provided` in the recommendation output and continue without blocking

---

## Step 3 — Table & Attribute Verification via MCP

### Table Existence Check (Multi-Environment)
For each unique `Physical(Technical) Table Name` in DAT:
1. Query all accessible environments via MCP Databricks SQL. Substitute your project's actual per-environment catalog names (read from the manifest if provided) for `{env}_catalog` below:
   ```sql
   SELECT table_catalog, table_schema, table_name
   FROM system.information_schema.tables
   WHERE table_catalog = '{env}_catalog'
     AND LOWER(table_name) IN ('table1', 'table2', ...)
   ```

3. Record verification status per environment:
   - ✅ Verified — table exists
   - ❌ Not Found — table missing
   - ⚠️ Pending — MCP connection unavailable for that environment

### Attribute Existence Check
For each DAT row with a verified table (exists in at least one environment):
1. Query table schema via MCP for each environment where table exists:
   ```sql
   SELECT column_name, data_type
   FROM system.information_schema.columns
   WHERE table_catalog = '{env}_catalog'
     AND table_schema = '<schema>'
     AND table_name = '<table>'
   ```
2. Check if `Physical Attribute Name` exists in returned column list (case-insensitive)
3. Missing attributes in any environment → flag with environment-specific status

### Environment-Specific Schema Naming
Environment/schema naming conventions vary by project (e.g. separate base vs. view schemas per environment, or an environment suffix). Read the actual convention from the manifest or DAT if provided; otherwise ask the user before assuming a naming pattern.

### MCP Unavailability Fallback
If MCP is unavailable, mark all table/attribute verification as `⚠️ PENDING` with a warning. Do not block the assessment — the agent can retry.

---

## Step 4 — Required System Identifier Extraction

### SourceSystemId
- Extract numeric Sys ID from DAT `Source of Origin` or `Data Source for Assessment` columns
- Look for patterns: numeric IDs, "Sys ID", "SystemId", "System ID = NNN"
- Must always be extracted — if not found, flag as `❌ NOT FOUND`
- Use your project's actual identifier column name (e.g. `XTNDFSystemId`) if one is defined in the repo's data-modeling standards

### ReportingUnitId
- Extract secondary dimension ID from same columns (`Source of Origin`, `Data Source for Assessment`)
- Look for: "Reporting Unit", "RU ID", secondary numeric identifiers
- If absent, mark as `NOT FOUND` (this is expected in some cases but must be explicitly noted)
- Use your project's actual identifier column name (e.g. `XTNDFReportingUnitId`) if one is defined in the repo's data-modeling standards

---

## Step 5 — Generate Markdown Report

After all processing, generate the assessment markdown using the fixed template from `references/OUTPUT_TEMPLATE.md`.

1. Fill all template variables from extracted data, including the `Data_Dictionary.csv` path when present
2. Build tables row-by-row from in-memory data structures, including PK/FK and data-type inference rows sourced from the data dictionary when matched
3. Calculate scorecard metrics
4. Determine exit status based on critical check results:
   - PASSED: All critical checks pass
   - BLOCKED: Any critical check fails
5. Save to `harness/specs/{use_case}/drd-dat-assessment.md`

---

## Key Processing Rules

1. **No Python scripts** — Read CSVs via `read_file`, parse in memory, generate markdown directly
2. **No hallucination** — Only use data found in provided xlsx/csv files and MCP query results
3. **No user interaction** — After file discovery, complete entire workflow autonomously
4. **Case-insensitive matching** — All column name and attribute comparisons are case-insensitive
5. **Handle quoted CSV fields** — Fields containing commas are wrapped in quotes
6. **MCP required** — Table/attribute verification needs active MCP Databricks connection
