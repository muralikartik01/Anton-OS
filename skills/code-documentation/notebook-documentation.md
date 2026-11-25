# Skill: Notebook documentation

**Used by:** Transformation Agent (read-only on the notebooks it documents).

**Purpose:** For every generated notebook, write a transformation document that states what the code does — so a reviewer can check the code against the approved mapping without reading SQL.

**Adapted from:** `skills/tiger-library/code-documentation/SKILL.md` and `skills/tiger-library/code-documentation/template.md` (section order, "document only what the code shows", `N/A` for absent items). Tiger's `target_config` dictionary, SCD2/XTN control-column section, audit/lineage section and header version-history parsing are dropped; DB-Kit notebooks are SQL notebooks whose facts come from the header cell, the variable block and the canonical SQL.

## Inputs

A generated notebook under `artifacts/generated-code/<project-id>/<run-id>/{bronze,silver}/` and the approved `source-to-target-mapping.yaml` it implements.

## Procedure

Read the notebook top to bottom and populate the sections below. **Do not edit the notebook.** Document only what the code shows: never infer intent, invent values or copy from the mapping what the SQL does not contain. Write `N/A` when something is absent (no filter, no join, no merge key).

1. **Overview** — notebook filename, path, layer (Bronze/Silver), target table (three-level name as parameterized, e.g. `{catalog}.{schema}.dim_customer`), purpose from the header cell.
2. **Source tables** — physical tables in `FROM`/`JOIN` (exclude CTEs and temp views): catalog/schema variable names, table name, alias, role.
3. **Target load config** — load strategy (upsert / append / delete-insert) and the key columns (merge key or PK) exactly as in the header comment and write step; quarantine table if any.
4. **Filters** — every `WHERE`/`QUALIFY`/`HAVING` and null-key/dedup step, each as a fenced `sql` block with a one-line purpose.
5. **Join logic** — one row per join: type, left, right, full `ON` condition.
6. **Transformation logic** — every column in the final `SELECT`, grouped (a column appears in exactly one group):
   - **Direct** — passed through unchanged.
   - **Cast** — `CAST`/`TRY_CAST`/rename, with the expression.
   - **Derived business rule** — `CASE`, arithmetic, lookups via join, window logic; cite the rule text from the mapping row only if the SQL implements it.
   - **Hardcoded default** — literals (`'UNKNOWN'`, `0`, `NULL`).
   - **Ingestion metadata** — `_ingested_at`, `_source_table` and any run/batch id taken from widgets.
7. **Footer** — `Mapping rows:` the ids of every mapping row the documented columns came from, and `Generated from:` the notebook path. A column with no mapping row is listed as `no mapping row` (a review finding, not something to hide).

## Output

`artifacts/generated-code/<project-id>/<run-id>/docs/<table>_transformation.md`, one per notebook, headings in the order above. Migration review checks that every notebook has one and that nothing in it is unsupported by the code.
