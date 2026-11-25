# Skill: Migration review

**Used by:** Review Agent.

**Purpose:** Produce the final release-readiness summary from everything the run has already produced — no new checks, just a disciplined read of the evidence.

**Adapted from:** `skills/tiger-library/code-review-tiger/SKILL.md` (its shared review categories and severity ranking), `skills/tiger-library/code-documentation/SKILL.md` (its discipline of documenting only what the code shows) and the check tables of `skills/tiger-library/code-optimization/SKILL.md` (see Code optimization checks). Every Tiger-audit-framework-specific check (`log_audit_data`, `cdo_dq_framework`, Tiger parameter widgets, Tiger naming) is dropped, since DB-Kit doesn't generate against that framework.

## Procedure

1. Confirm every step in the workflow template actually completed (per the run record) — a skipped or blocked step is a release blocker.
2. Cross-check `results.md`: every planned rule/reconciliation check has an explicit status; any `fail` or `blocked` is a named risk in the final report.
3. Review generated code against `rules/` and these categories, recording each finding with a severity (`critical`|`high`|`medium`|`low`) — flag, don't silently fix (that's the Transformation Agent's job, in a new run):
   - **Delta/schema:** no `mergeSchema`/`overwriteSchema` without a stated reason; no full overwrite of a partitioned table without `replaceWhere`; explicit column lists, no `SELECT *`; casts explicit, with failures quarantined not dropped.
   - **Data quality/row validation:** null-key filter and de-duplication before MERGE; non-empty-source check before delete-insert; rows-written reported.
   - **Unity Catalog:** three-level names only; no `hive_metastore`, `USE CATALOG/SCHEMA`, or `dbfs:/` paths; catalog/schema parameterized, not hardcoded.
   - **Observability/hygiene:** no `display()`/`show()`/stray `print()` or commented-out debug code in the main path; no secrets or widget values printed.
   - **Notebook cell structure:** `%md` section headers; DML via `spark.sql()` in Python cells, not `%sql`; no `%sh`, `%fs` or `%pip`.
   - **SQL integrity:** the SQL in each notebook is textually identical to what `execute_statement` ran (compare against the run record/results).
4. Compute a 0–100 compliance score: start at 100, subtract 25 per critical, 10 per high, 4 per medium, 1 per low (floor 0). The score informs, but never overrides, an explicit blocker.
5. Document only what the artifacts show: never invent values, row counts, owners or dates; mark absent facts as "not provided".
6. Restate every open assumption/question from discovery or blueprinting that was never resolved.
7. Conclude with an explicit "ready" / "not ready" release-readiness call and why. Any critical finding, `fail`/`blocked` check, or unresolved blocker means "not ready".

## Code optimization checks

**Adapted from:** `skills/tiger-library/code-optimization/SKILL.md` (check IDs, priorities and wording kept). PySpark/Python-only domains (P, Q) and checks that need a Python runtime or streaming (P*, Q*, S10/S11 style-only, D7-D9, D11, D13, SEC2/SEC4/SEC6/SEC7/SEC9, DQ9) are dropped because DB-Kit notebooks are generated SQL carried in `spark.sql()`. Run each applicable check on every generated notebook; record each hit as a finding (check ID, notebook, cell/line) using the severity mapping below, so it feeds the 0-100 score in Procedure step 4. Never auto-fix.

Priority mapping: Critical = `critical`, High = `high`, Medium = `medium`, Low = `low`.

**SQL (S)**

| ID | Check | Priority |
|---|---|---|
| S1 | `SELECT *` in a production query | Critical |
| S2 | Query on a large table with no `WHERE`/bounded scope (full scan) where the load is meant to be incremental | Critical |
| S3 | Nested subquery where a CTE would be clearer | High |
| S4 | Non-sargable predicate: function applied to a partition/clustering column in `WHERE` | High |
| S5 | Implicit type cast in a `JOIN` condition | High |
| S12 | `NOT IN` with a subquery: use `NOT EXISTS` / `LEFT ANTI JOIN` | High |
| S13 | Implicit join syntax (`FROM a, b WHERE ...`) | High |
| S14 | `UNION` where `UNION ALL` suffices | High |
| S15 | Correlated subquery in `SELECT`/`WHERE` | High |
| S6 | `DISTINCT` without clear necessity | Medium |
| S7 | `ORDER BY` without `LIMIT` on a large result | Medium |
| S8 | `HAVING` filtering rows that belong in `WHERE` | Medium |
| S9 | Complex query not decomposed into CTEs | Medium |
| S16 | Window function missing explicit frame | Medium |
| S17 | Join type not stated explicitly | Medium |
| S18 | Multiple aggregations of the same table in separate queries | Medium |

**Delta (D)**

| ID | Check | Priority |
|---|---|---|
| D1 | MERGE target fully scanned: missing or broad join predicate | Critical |
| D2 | Write with `mergeSchema`/`overwriteSchema` used carelessly | Critical |
| D14 | `INSERT OVERWRITE`/overwrite of a partitioned table without `replaceWhere` | Critical |
| D3 | No `OPTIMIZE`/`ZORDER BY` (or liquid clustering) on frequently filtered columns of a large table | High |
| D4 | `VACUUM` not planned for the table | High |
| D5 | Table expected to exceed 1 GB created without partitioning/clustering | High |
| D6 | Overwrite without idempotency guard or `replaceWhere` | High |
| D12 | No `NOT NULL`/`CHECK` constraints on keys and required columns | High |
| D15 | Full-sync MERGE missing `WHEN NOT MATCHED BY SOURCE` handling | High |
| D17 | MERGE condition omits partition columns (no pruning) | Medium |
| D10 | Table or column missing `COMMENT` | Low |
| D16 | Liquid clustering not considered for tables with several high-cardinality filter columns | Low |

**Security (SEC)**

| ID | Check | Priority |
|---|---|---|
| SEC1 | Widget/user input interpolated into SQL without validation (identifiers must match an allow-list pattern) | Critical |
| SEC3 | Secrets, tokens or passwords printed or logged | Critical |
| SEC5 | Wildcard Unity Catalog grants (`GRANT ALL ... *`) | High |
| SEC10 | Hardcoded SAS token / access key in code | High |
| SEC8 | Stack trace or internal path surfaced in notebook output | Medium |

**Data quality (DQ)**

| ID | Check | Priority |
|---|---|---|
| DQ1 | No null check on join/merge keys before the join | Critical |
| DQ2 | No schema validation after reading the source | High |
| DQ3 | Implicit cast that may silently truncate or overflow | High |
| DQ4 | Duplicates not removed before writing to the target | High |
| DQ5 | No row-count assertion after a critical transformation | High |
| DQ6 | Date/timestamp parsed without explicit format | Medium |
| DQ7 | String keys not trimmed before join/comparison | Medium |
| DQ8 | Aggregation not validated against an expected range | Medium |
| DQ10 | Column types not explicitly cast after a join or union | Medium |
| DQ11 | No source-vs-target row-count reconciliation after load | Low |

Where a check overlaps a category already listed in Procedure step 3 (for example `SELECT *`), record it once.

## Documentation checks

1. Every notebook under `generated-code/<project-id>/<run-id>/{bronze,silver}/` has a matching `docs/<table>_transformation.md` (`skills/code-documentation/notebook-documentation.md`). A missing doc is a `high` finding.
2. No statement in a doc is unsupported by the code: spot-check each documented filter, join, cast, default and key against the notebook's canonical SQL. Any claim the SQL does not show is a `high` finding; a doc footer that cites no mapping-row ids is `medium`.

## Output

`migration-report.md` following spec §13's 10-point structure, under `artifacts/reports/<project-id>/<run-id>/`, including the findings table (category, severity, location, recommendation) and the compliance score.
