---
name: sttm-to-sql
description: Generate production-ready SQL from STTM using NorthStar project conventions.
---

# Skill: Generate SQL from STTM

## Purpose

Generate production-ready SQL from a Source-to-Target Mapping (STTM) document.

The SQL must implement the STTM logic exactly and comply with NorthStar project conventions or any specified project standards.

---

## Required Inputs

The request must provide:

1. STTM file path(s) under `dataengineering/sttm/...`
2. Matching config JSON path(s) under `dataengineering/config/...`
3. Output root path (default: `dataengineering/sql/...`)
4. Optional exclusion list of STTM files to skip

If any required input is missing, infer it from the filename and subfolder patterns used in this repository.

---

## STTM Elements to Parse

Read and implement all relevant STTM content, including:

- Source tables and source columns
- Join conditions
- Filters and applicable conditions
- Direct mappings
- Derived and transformed mappings
- Business rules and comments that define the logic
- Aggregations and Group By columns
- Default values
- Target columns and target data types
- Merge key and primary key flags used to derive hash key logic

Treat the STTM as the source of truth.

---

## Repository References

Before generating SQL:

1. Study STTM patterns under:

`dataengineering/sttm/`

Examples of folder patterns include:

- `nl-netherlands`
- `fr-france`
- `es-spain`
- `promo` and `promotions`

Use the folder structure and processing notes as the primary reference for identifying parallel STTM patterns and related logic.

The processing files are the reference documents provided by the DG team for validation and implementation guidance. First, review the STTM. If the logic is described in the JDA Joining Condition or Processing Notes column, use that as the source of truth. If the logic remains unclear, review the related links or reference Python notebooks for deeper context.

For the `Target Data Transformation Rules` column, any value other than `No Mapping` or blank must be reflected in the corresponding target table columns.

2. Study the matching config JSON flow under:

`dataengineering/config/`

3. Use the existing gold implementation style as a reference:

`dataengineering/gold/`

4. Reuse common transformation intent from utility functions where needed:

`dataengineering/utils/`

Review the utility and common_utils notebooks to understand the environment variables and function definitions used across the configuration files.

---

## SQL Generation Rules

1. Every target column must be generated.
2. Every direct mapping must be preserved.
3. Every derived or transformed expression must be preserved exactly.
4. Every join condition must be preserved.
5. Every filter or applicability condition must be preserved.
6. Every aggregation and Group By rule must be preserved.
7. Every default value rule must be preserved.
8. If the STTM says `No Mapping`, output the target column as `NULL AS <TargetColumn>` unless a default is explicitly specified.
9. If the STTM defines hash keys (HK/checksum/unique keys), implement them using the exact column set and order.
10. If the STTM and config conflict, prefer the STTM for target column mapping and expression; use the config for source flow and join orchestration context.

---

## SQL Structure Standard

Use this structure unless the STTM explicitly requires another shape:

1. `WITH` CTE for each logical extraction or mapping step.
2. Intermediate CTEs for reusable derived expressions.
3. Final `SELECT` that outputs all target columns in target table order.

Recommended pattern:

```sql
WITH src AS (
        -- base extraction
),
step_1 AS (
        -- joins / filters
),
step_2 AS (
        -- derived reusable fields
)
SELECT
        -- all target columns in order
FROM step_2;
```

---

## Coding Standards

1. Generate readable SQL with consistent indentation.
2. Use meaningful aliases.
3. Avoid duplicate calculations; compute once and reuse.
4. Avoid unnecessary nested queries.
5. Keep functions and casting aligned with the project dialect (Databricks/Spark SQL when required).
6. Keep naming consistent with STTM target columns, including case-sensitive or special names.

---

## Output File Rules

1. Output SQL file path must mirror the STTM subfolder path.
2. Output filename should match the STTM filename with `_sttm` removed.

Examples:

- `dataengineering/sttm/promotions/es_arch3_snacks_ot_sttm.csv`
  -> `dataengineering/sql/promotions/es_arch3_snacks_ot.sql`

- `dataengineering/sttm/financials/periodic/fr_arch3_snacks_all_sttm.csv`
  -> `dataengineering/sql/financials/periodic/fr_arch3_snacks_all.sql`

3. Respect requested exclusions exactly.

---

## Validation Checklist (Mandatory)

Before finalizing each SQL file, verify:

- All source tables from the STTM are represented.
- All joins are implemented.
- All filters are implemented.
- All business rules are implemented.
- All target columns are present.
- No mapped target column is missing.
- Aggregations are correct.
- Group By columns are complete.
- `No Mapping` targets are represented as `NULL` (or as the default value when defined).

---

## Response Contract

When the user asks to generate SQL:

1. Create SQL files directly in the workspace at the requested target location.
2. Return a concise completion summary with the generated file list.
3. Do not return explanatory prose unless the user asks for it.

---

## Output Content Restriction

Generate only SQL in generated `.sql` files.

Do not generate:

- JSON
- Spark/Python code
- Narrative explanations inside SQL files

SQL must be production-ready.

## Notes for Integration with `sql-to-json`

This skill is a recommended precursor for `sql-to-json` when users provide STTM input but no SQL exists. Agents implementing `sql-to-json` should consider invoking this skill automatically when:

- A matching SQL file under `dataengineering/sql/` is missing for the requested target and an STTM exists under `dataengineering/sttm/`.
- The user request mentions STTM file paths or references transformation logic that exists only in the STTM.

When auto-invoked by `sql-to-json`, this skill should:

- Produce readable Databricks/Spark SQL in the expected output path, mirroring the STTM folder structure.
- Return the generated SQL file path(s) to the caller.
- Fail fast with a clear error message if required STTM fields are missing or ambiguous.