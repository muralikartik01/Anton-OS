# Skill: Generate Transformation Documentation from a Databricks Notebook

## Description
This skill generates a structured transformation documentation `.md` file from a Tiger Databricks Python notebook (`.py`). The generated document follows the standard template defined in `template.md` within this folder.

---

## How to Invoke

Ask Copilot:

> "Generate transformation documentation for `<path-to-notebook.py>`"

or shorthand:

> "doc `<path-to-notebook.py>`"

---

## Input

| Input | Description |
|---|---|
| **Notebook file** | A Databricks Python notebook (`.py`) typically located under `databricks/` |

---

## Output

A Markdown file (`.md`) placed **in the same directory** as the source notebook, named:

```
<original_filename>_transformation.md
```

**Example:**  
Input: `snp_materialmaster_europe_common_layer0.py`  
Output: `snp_materialmaster_europe_common_layer0_transformation.md`

---

## What Copilot Must Extract

Work through the notebook top-to-bottom and populate each section from the template:

### Section 1 — Overview
Populate from file metadata and the notebook header markdown (`%md`) cell:
- Notebook filename
- Notebook file path (relative to repository root)
- Layer name (e.g., Layer 0, Silver → Gold)
- Sector/domain
- Created by, created date, last updated date (from Version History table in the header)

### Section 2 — Source Tables
Extract from `FROM` and `JOIN` clauses in all SQL blocks.
**Only include tables that have a Catalog and Schema variable defined (physical tables). Exclude CTEs, Temporary Views, and Subqueries.**

- Catalog variable name
- Schema variable name
- Physical table name
- Alias (if useful for context)
- Brief description of the table's role

### Section 3 — Target Load Configuration
Extract entirely from the `target_config` dictionary in the notebook:

| target_config key | Maps to sub-section |
|---|---|
| `target_db_name` | 3.1 Target Table — Database Variable |
| `target_table_name` | 3.1 Target Table — Table Name |
| `step` | 3.1 Target Table — Step |
| `load_type` | 3.2 Load Type |
| `load_changed_data` | 3.2 Load Type |
| `target_key_columns` | 3.3 Key Columns |
| `exclude_compare_columns` | 3.4 Merge/Compare Columns Excluded |
| `exclude_update_columns` | 3.5 Delete Condition — Exclude Update Columns |
| delete_criteria | 3.5 Delete Condition |
| target_partition_filter | 3.5 Partition Filter |

### Section 4 — Filter Conditions
Extract all `WHERE`, `QUALIFY`, and `HAVING` conditions from SQL blocks:
- Runtime parameter-based filters (e.g., `systemid IN {var_systemid_filter}`)
- Deduplication logic (`QUALIFY ROW_NUMBER() OVER (...)`)
- Hard-coded filter values
- Present as sub-sections (4.1, 4.2, ...) per filter type

### Section 5 — Join Logic
Extract all `JOIN` clauses:
- Join type (INNER, LEFT, RIGHT, FULL)
- Left and right table names / aliases
- Full join condition (`ON` clause)

### Section 6 — Transformation Logic
Analyse every column in the `SELECT` statement and categorise:

| Sub-section | Category | Rule |
|---|---|---|
| 6.1 | Conditional Mappings/Case conditions | Columns selected differently based on `if/elif` market/condition logic |
| 6.2 | SCD2 Control Columns | `XTNValidFromDate`, `XTNValidToDate`, `RecordActiveStatusFlag` or equivalents |
| 6.3 | Direct Column Mappings | Source column = target column, no transform |
| 6.4 | Cast / Type Conversion | Columns using `CAST`, `TRY_CAST`, renaming |
| 6.5 | Lookup / Reference Columns | Columns sourced from a joined/reference table |
| 6.6 | Hardcoded / Defaulted Columns | Literal values (`'UNK'`, `0`, `NULL`) in SELECT |
| 6.7 | Audit / Lineage Columns | Python runtime variables injected as SQL literals (`job_id`, `var_current_timestamp`, `var_market_name`) |

---

## Rules

1. **Do not invent values.** Only document what is explicitly present in the notebook code.
2. Use `N/A` or `Not configured` when a `target_config` key is absent or empty (`[]`, `None`).
3. Resolve variable names where possible — e.g., if `db_mapping['gold_l0_dim_db']` appears in comments or header as `snp_procurement_wide_gold`, include both.
4. Place all SQL filter examples inside fenced code blocks (` ```sql `).
5. Follow the section numbering and heading style defined in `template.md` exactly.
6. Output file must be valid GitHub-flavoured Markdown.
