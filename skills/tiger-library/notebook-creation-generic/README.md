# Skill — Notebook Creation Generic: Simplified Databricks Notebook Generator

## Overview
This skill generates a **simplified, standalone** Databricks Gold layer notebook (`.py`) from a
Source-to-Target Mapping (STTM) CSV, with **no dependency on PepsiCo-specific frameworks**.

### How it differs from `notebook-creation`

| Feature | `notebook-creation` | `notebook-creation-generic` |
|---|---|---|
| Framework dependencies | `cdo_audit_framework_wd_la`, `cdo_dq_framework` | None — stdlib + PySpark only |
| Utility notebooks | `%run ./notebook_common_utils` | Not used |
| Widget count | 7 (JSON project_params / additional_params) | 1 (`job_id` only — injected by Workflows) |
| Audit logging | `au.log_audit_data()` (PepsiCo framework) | Direct Delta table write |
| DQ Framework | `dqm_framework.dq_framework_invoke()` | Not included |
| System ID validation | `check_for_systemid_reporting_id()` | Not included |
| Notebook sections | 29 | 10 |
| Use case | Full Tiger production pipelines | Generic / standalone / quick-start pipelines |

---

## Trigger Phrases (Distinct from `notebook-creation`)

`generic notebook` · `simple notebook` · `generic etl` · `quick notebook` ·
`standalone notebook` · `lightweight notebook` · `create generic notebook` ·
`generic gold` · `simple etl` · `notebook template` · `basic notebook`

---

## What It Produces

A complete Databricks `.py` notebook with:
- Magic Markdown header (project name, purpose, source/target, load strategy, version history)
- 1 widget (`job_id` — injected by Databricks Workflows)
- Environment derived from cluster name (split on `_`, extract `dev` / `qa` / `prod`)
- Target table name and audit table defined as variables in the variable block
- Explicit variable block listing input tables, gold DB, merge keys, system IDs, load strategy
- `spark.read.table()` source reads registered as temp views
- Spark SQL transformation block with columns derived from STTM mappings
- Mandatory XTN audit columns appended to every SELECT
- Upsert (DeltaTable.merge) / Append / Delete-Insert write logic based on STTM
- Direct Delta audit table write (non-fatal on failure)
- `dbutils.notebook.exit()` / `raise Exception` exit handler

---

## Key Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Full skill definition, STTM parsing rules, generation steps |
| `references/_generic__table_name___layer__to_gold.py` | Base template all notebooks extend |
| `evals/evals.json` | Test cases for validating skill output quality |

---

## Input Files
- `Output/STTM_DDL_creation/*.csv` — Source-to-Target Mappings (required)
- `Output/STTM_DDL_creation/*.sql` — Target DDL (optional, for type cross-check)

---

## Related Skills

| Skill | Use When |
|-------|---------|
| `notebook-creation` | Full Tiger production pipeline with PepsiCo framework stack |
| `code-documentation` | Document the generated notebook |
| `create-unit-test-cases` | Write unit tests for the generated code |
| `code-review` | Validate the notebook against Tiger coding standards |

---

## Quick Start Example

**User says:** `create generic notebook for OperationalExpenseInvoiceFlattened silver to gold`

**Copilot will:**
1. Read `Output/STTM_DDL_creation/*.csv` for the matching table
2. Extract sources, targets, merge keys, system IDs, transformations
3. Detect load strategy (Upsert / Append / Delete-Insert) from STTM merge key pattern
4. Generate `opex_operational_expense_invoice_flattened_silver_to_gold.py`
5. Write output to `Output/CodeGeneration/`

---

## Coding Standards Enforced

- PEP 8 / 120-character line limit
- No hardcoded values — target table and catalog paths set in variable block; env derived at runtime
- No `display()`, `show()`, `count()` in production cells
- Unity Catalog three-part names (`catalog.schema.table`) throughout
- `try/except` with `status = "Failed"` on all data operations
- `select()` over chained `withColumn()`
- No UDFs — native Spark SQL functions only
- SQL injected via `.format()` not f-strings inside triple-quoted SQL
- Audit log failure is non-fatal — does not override load success status
