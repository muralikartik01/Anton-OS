# Skill 07 — Notebook Creation: Databricks Notebook Generator

## Overview
This skill generates production-ready Databricks Gold layer notebooks (`.py`) by
reading Source-to-Target Mapping (STTM) files and applying PepsiCo DTV Global
Data Engineering standards.

## Trigger Phrases
`build`, `notebook`, `create notebook`, `new notebook`, `code`, `generate code`,
`etl notebook`, `silver to gold`, `bronze to gold`

## What It Produces
A complete Databricks `.py` notebook file with:
- Magic Markdown header (project name, purpose, creator, version history, source/target table info, system IDs)
- Standard utility and variable notebook `%run` commands
- Grouped imports (stdlib → PySpark → PepsiCo frameworks)
- Widget-based parameter handling (no hardcoded values)
- JSON parameter parsing (`project_params`, `additional_params`)
- Full variable declaration block with audit framework setup
- Transformation SQL derived from STTM column mappings
- System ID / Reporting Unit ID validation
- DQ Framework integration hook
- Gold write operation (Upsert / Append / SCD2 / Delete-Insert)
- Statistics capture
- Notebook exit / error escalation

## Key Files

| File | Purpose |
|---|---|
| `SKILL.md` | Full skill definition, STTM parsing instructions, generation process |
| `assets/code-build-template.md` | Fully populated example notebook |
| `assets/sttm-parsing-guide.md` | Detailed STTM column → notebook field mapping |
| `references/_project_code_abrrev__table_name___layer__to_gold.py` | Base template all notebooks extend |
| `evals/evals.json` | Test cases for validating skill output quality |

## Input Files
- `Output/STTM_DDL_creation/*.csv` — Source-to-Target Mappings
- `Output/STTM_DDL_creation/*.sql` — Target table DDL (for column type reference)

## Related Skills
| Skill | Use When |
|---|---|
| `code-documentation` | Document the generated notebook |
| `create-unit-test-cases` | Write unit tests for the generated code |
| `data-modeling` | Validate data model before STTM-based code build |
| `icedq-rule-creation-publish` | Publish DQ rules aligned with STTM transformations |

## Quick Start Example

**User says:** `build notebook for CostedBOM silver to gold`

**Copilot will:**
1. Read `Output/STTM_DDL_creation/CostedBillOfMaterialsFinanceApproach_STTM_v1.csv`
2. Extract sources, targets, merge keys, system IDs, transformations
3. Generate `cbom_costed_bill_of_materials_finance_approach_silver_to_gold.py`
4. Place output in `Output/CodeGeneration/`

## Coding Standards Enforced
- PEP 8 / 120-character line limit
- No hardcoded values — all params from JSON widgets
- No `display()`, `show()`, `count()` in production
- Unity Catalog three-part names throughout
- `try/except` with `au.log_audit_data()` on all data operations
- `select()` over chained `withColumn()`
- No UDFs when native Spark functions available
