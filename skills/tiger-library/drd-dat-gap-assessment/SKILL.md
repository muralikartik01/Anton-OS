name: drd-dat-gap-assessment
description: Validates DRD and DAT xlsx files for mandatory column completeness, table/attribute existence via Databricks MCP, required system-identifier extraction, and advisory primary-key/data-type inference from the DAT data dictionary. Invoked exclusively by the drd-dat-assessor agent.
---

# DRD / DAT Gap Assessment Skill

Validates DRD/DAT workbooks against the repository's DRD/DAT standards. Converts Excel to CSV, checks column schemas, verifies tables/attributes via Databricks MCP, extracts required identifier fields, and enriches recommendation output from the DAT `Data_Dictionary` sheet when available.

## Inputs
- DRD `.xlsx` file (path provided via `specs/{use_case}/manifest.md`)
- DAT `.xlsx` file (path provided via `specs/{use_case}/manifest.md`)
- DAT `Data_Dictionary` sheet converted to `specs/{use_case}/csv/DAT/Data_Dictionary.csv` when present in the workbook
- Active MCP Databricks connection (for table/attribute verification)

## Dependencies
- **excel-to-csv** — converts xlsx to CSV before parsing
- **Databricks MCP** — required for table and attribute existence checks

---

## Critical Checks (Gate Blockers)

### 1. DRD Column Template Match
All 24 expected DRD columns must exist in header (see `references/COLUMN_SCHEMAS.md`).
Of the 8 mandatory columns, these 5 must also have ≥80% non-blank rows:
`Sector`, `Business Unit`, `Market Unit`, `Data Grain`, `Subject Area Attributes Required`

### 2. DAT Column Template Match
All 29 expected DAT columns must exist in header (see `references/COLUMN_SCHEMAS.md`).
Of the 7 mandatory columns, these 4 must also have ≥80% non-blank rows:
`Source of Origin`, `Data Source for Assessment`, `Physical(Technical) Table Name`, `Physical Attribute Name`

### 3. Table & Attribute Verification (MCP)
For each unique `Physical(Technical) Table Name` in DAT:
- Query `system.information_schema.tables` across all accessible environments (DEV, QA, P2D, PROD)
- For verified tables, check each `Physical Attribute Name` against `system.information_schema.columns`
- Flag missing tables/attributes per environment
- If MCP unavailable → mark as `⚠️ PENDING`, do not block

### 4. Required System Identifier Extraction (Mandatory)
- Scan ALL columns in the DAT template for numeric system-identifier patterns, including repository-specific names such as `SourceSystemId` (or your project's equivalent, e.g. `XTNDFSystemId`) when present
- A required system identifier must always be extracted — if not found in any column, the gate is BLOCKED

---

## Recommendations (Non-Critical)

- **Reporting-unit identifier** — extract the secondary dimension ID from `Source of Origin` / `Data Source for Assessment`; use the repository-specific field name such as `ReportingUnitId` (or your project's equivalent, e.g. `XTNDFReportingUnitId`) when present, and mark `NOT FOUND` if absent
- **Fill rate for advisory columns** — report fill % for `Data Quality Expectations from the Stakeholders`, `Business Rules` (DRD), and `Scenario Assessed` (DAT)
- **UC 3-part naming** — flag tables not in `catalog.schema.table` format; suggest corrected path
- **Business definition coverage** — report % of attributes with filled `Attribute Business Definition`
- **PK/FK and data type inference** — when `Data_Dictionary.csv` is present, match DAT `Physical Attribute Name` and `Physical(Technical) Table Name` to `Field Name / Attribute Name (Technical)` and `Source / Table Name`; infer advisory `Primary Key / Foreign Key` plus source data type from `Data Type`, `Length`, and `Scale`; use DRD `Data Grain` and DAT gap status as fallback context, and mark unmatched rows as `NOT INFERRED`

---

## Output

Single markdown file saved to: `harness/specs/{use_case}/drd-dat-assessment.md`
- Uses fixed template from `references/OUTPUT_TEMPLATE.md` — structure is always identical
- No HTML output. No intermediate scripts.
- CSVs are written to `specs/{use_case}/csv/DRD/` and `specs/{use_case}/csv/DAT/`

---

## Gate Criteria (4 checks)

| Gate | Condition |
|------|-----------|
| `drd_template` | All 24 DRD columns exist; 5 critical mandatory columns have ≥80% fill |
| `dat_template` | All 29 DAT columns exist; 4 critical mandatory columns have ≥80% fill |
| `mcp_table_verified` | All DAT tables verified in at least one MCP environment |
| `required_identifier_extracted` | Required system identifier successfully extracted |

**PASSED** = all 4 exit criteria met
**BLOCKED** = any criterion fails

---

## Key Rules
1. No Python scripts — read CSVs via `read_file`, parse in memory, generate markdown directly
2. No hallucination — only use data from provided files and MCP query results
3. No HTML output — only markdown in `harness/specs/{use_case}/`
4. Do NOT scan codebase for CSV/XLSX files — use only paths from the manifest
5. Data dictionary inference is advisory only — absence of `Data_Dictionary.csv` never blocks the assessment

## References
- `references/WORKFLOW.md` — full step-by-step processing logic and SQL queries
- `references/COLUMN_SCHEMAS.md` — complete column lists and fill-value rules
- `references/OUTPUT_TEMPLATE.md` — fixed markdown output template
- `references/Data-Modeling-Standards.md` — repository naming and audit column standards
