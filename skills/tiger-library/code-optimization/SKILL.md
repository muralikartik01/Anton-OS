---
name: code-optimization
description: 'Comprehensive code optimization and performance review for PySpark, Python, SQL, and Databricks notebooks. Use when: optimize code, full code optimization, all optimizations, code optimization review, optimize notebook, optimize script, optimize sql, optimize python, optimize databricks, performance review, end-to-end code review, comprehensive review, full review, optimize all, pyspark optimization, pyspark review, spark performance review, optimize pyspark, spark optimization, pyspark audit, performance audit, review pyspark script, review databricks notebook, pyspark health check, spark code review, pyspark security review, audit notebook, review this file, check pyspark, python performance, sql performance, delta optimization, databricks performance tuning, security review, data quality review, streaming optimization, code security check, spark streaming review, data quality check, quality review, null check, schema validation, skew detection, spark skew, salting, data skew.'
argument-hint: 'Path to .py, .sql, or .ipynb file(s) to review'
---

# Code Optimization Skill

## Purpose

Perform a comprehensive performance, optimization, data quality, and code quality review across **PySpark**, **Python**, **SQL**, and **Databricks / Delta Lake** code. Outputs a numbered findings table, a health score, and on-demand before/after fix blocks — **no changes are applied automatically**.

---

## When to Use

Trigger this skill whenever the user says any of:
`optimize code`, `optimize notebook`, `optimize script`, `optimize sql`, `optimize python`, `optimize databricks`, `full code optimization`, `performance review`, `pyspark optimization`, `spark performance review`, `pyspark audit`, `performance audit`, `review pyspark`, `review databricks notebook`, `pyspark health check`, `check pyspark`, `end-to-end code review`, `comprehensive review`, `full review`, `spark optimization`, `delta optimization`, `python performance`, `sql performance`, `audit notebook`, `review this file`

---

## Input Requirements

| Input | Details |
|---|---|
| **File Path(s)** | Absolute or workspace-relative path to `.py`, `.sql`, or `.ipynb` file(s) |
| **Review Scope** *(optional)* | e.g. `pyspark only`, `sql only`, `all` (default: all domains) |

**Auto-detection rules:**
- `.py` containing `spark` / `pyspark` imports → PySpark + Python + Delta checks
- `.py` without Spark imports → Python-only checks
- `.sql` → SQL Optimization checks only
- `.ipynb` → parse cells; apply domain checks per cell language

---

## Workflow

### Phase 1 — Load File

1. Read the file(s) provided by the user.
2. Detect file type and applicable check domains.
3. Confirm scope with the user if ambiguous.

---

### Phase 2 — Analysis

Run every applicable check from the four domains below against the file. Assign each violation a **finding number**, **category**, **priority**, **file name**, and **location** (function name, line number, or cell number).

---

## Check Domains

### Domain 1 — PySpark Performance

| # | Check | Priority |
|---|---|---|
| P1 | `collect()` called on a large or unbounded DataFrame | Critical |
| P2 | `.rdd` conversion used (triggers full deserialization) | Critical |
| P3 | Python UDF used where a native Spark / SQL function exists | Critical |
| P4 | `show()` or `display()` called in production code | High |
| P5 | Multiple chained `withColumn()` calls — replace with a single `select()` | High |
| P6 | Cartesian join (cross join without explicit intent) | High |
| P7 | `pandas` DataFrame used instead of Spark DataFrame | High |
| P8 | Missing `broadcast()` hint for a small lookup / dimension table | High |
| P9 | Multiple `count()` calls on the same DataFrame | High |
| P10 | `cache()` / `persist()` missing on a DataFrame used more than once | Medium |
| P11 | No `coalesce()` before writing a small output file | Medium |
| P12 | No `repartition()` before a wide shuffle-heavy transformation | Medium |
| P13 | Partition pruning not leveraged (filter on non-partition column) | Medium |
| P14 | Delta MERGE without selective join keys (causes full target table scan) | Medium |
| P15 | `orderBy()` / `sort()` without a subsequent `limit()` | Low |
| P16 | `dropDuplicates()` missing before a join on potentially duplicate keys | Low |
| P17 | `filter()` / `where()` placed after a join instead of before (late pushdown) | Low |
| P18 | Window function missing `partitionBy` — entire dataset loaded into single partition | Critical |
| P19 | Data skew detected (one join key dominates) — no salting or skew hint applied | High |
| P20 | `toPandas()` called without a row-count guard — risk of driver OOM | High |
| P21 | `explode()` used on a large array column without prior filtering | High |
| P22 | `groupBy()` on a very high-cardinality column (risk of shuffle OOM) | High |
| P23 | Schema inference used on CSV/JSON source (`inferSchema=True`) — reads data twice | Medium |
| P24 | `cache()` / `persist()` called but `.unpersist()` never called — memory leak risk | Medium |
| P25 | `df.union()` used where `df.unionByName()` is safer (column order dependency) | Medium |
| P26 | `spark.sql()` string query used for logic that could be expressed as DataFrame API | Low |
| P27 | `DataFrame.isEmpty()` replaced by `count() == 0` — use native `.isEmpty` (Spark 3.3+) | Low |
| P28 | Unnecessary caching of single-use DataFrames — memory consumed with no reuse benefit | Medium |
| P29 | `SELECT *` followed by a downstream filter — unnecessary column deserialization before pruning | Medium |
| P30 | Not utilizing Z-ORDER columns in `WHERE` clause filters — partition pruning not leveraged | Medium |
| P31 | Attempting to broadcast a large table (> 2 GB) — driver OOM risk; remove or guard `broadcast()` hint | High |
| P32 | Redundant window specifications — same `partitionBy`/`orderBy` repeated across multiple window calls; define once and reuse | Medium |
| P33 | Multiple aggregation passes on the same DataFrame that could be combined into a single `groupBy` | Medium |
| P34 | `repartition()` followed by `sort()` — use `repartition(n, col)` for sort-aware, co-located partitioning | Medium |
| P35 | Recursive function without a base case or max-depth guard — stack overflow risk on large datasets | Medium |

---

### Domain 2 — Python Code Quality

| # | Check | Priority |
|---|---|---|
| Q1 | Hardcoded credential, secret, password, or API key in source | Critical |
| Q2 | SQL query built by string concatenation (SQL injection risk) | Critical |
| Q3 | Hardcoded table name, file path, or environment value (use widgets / config) | High |
| Q4 | `print()` statement used in production code (use logging) | High |
| Q5 | Unused import statement | High |
| Q6 | Missing `try/except` around critical operations (reads, writes, merges) | High |
| Q7 | Line exceeds 120 characters | Medium |
| Q8 | Function or method missing docstring | Medium |
| Q9 | Single-letter variable name outside of a simple loop | Medium |
| Q10 | PEP 8 violation (indentation, spacing, blank lines) | Medium |
| Q11 | Function with more than 5 parameters (consider refactoring) | Medium |
| Q12 | Missing type hints on function signatures | Low |
| Q13 | Dead code — commented-out block or unreachable statement | Low |
| Q14 | Inconsistent naming convention (mixed `camelCase` and `snake_case`) | Low |
| Q15 | Bare `except:` clause — catches all exceptions silently, hides real errors | High |
| Q16 | `eval()` or `exec()` used — arbitrary code execution security risk | Critical |
| Q17 | Mutable default argument in function definition (e.g., `def f(x=[])`) | High |
| Q18 | Deeply nested code — more than 3 levels of indentation (readability + logic risk) | Medium |
| Q19 | Function exceeds 50 lines — should be decomposed into smaller functions | Medium |
| Q20 | Script-level code not guarded by `if __name__ == "__main__":` | Medium |
| Q21 | Global mutable state / global variable modified inside a function | Medium |

---

### Domain 3 — SQL Optimization

| # | Check | Priority |
|---|---|---|
| S1 | `SELECT *` used in a production query | Critical |
| S2 | Query on a large table with no `WHERE` clause (full table scan) | Critical |
| S3 | Nested subquery where a CTE (`WITH` clause) would be clearer and faster | High |
| S4 | Non-sargable predicate — function applied to a partition or indexed column in `WHERE` | High |
| S5 | Implicit type cast in a `JOIN` condition (causes scan, disables pruning) | High |
| S6 | `DISTINCT` used without clear necessity (verify deduplication intent) | Medium |
| S7 | `ORDER BY` without `LIMIT` in a large result set | Medium |
| S8 | `HAVING` used to filter rows that could be filtered in `WHERE` | Medium |
| S9 | Complex query missing CTE decomposition (readability + optimizer hint) | Medium |
| S10 | SQL keywords not fully capitalised | Low |
| S11 | Inconsistent SQL formatting (alignment of `SELECT`, `FROM`, `JOIN`, `WHERE`) | Low |
| S12 | `NOT IN` with a subquery — use `NOT EXISTS` or `LEFT ANTI JOIN` (handles NULLs correctly) | High |
| S13 | Implicit join syntax (`FROM a, b WHERE a.id = b.id`) — use explicit `JOIN ... ON` | High |
| S14 | `UNION` used where `UNION ALL` is sufficient — unnecessary deduplication cost | High |
| S15 | Correlated subquery inside `SELECT` or `WHERE` — executes once per row (O(n) cost) | High |
| S16 | Window function missing explicit frame specification (`ROWS BETWEEN` / `RANGE BETWEEN`) | Medium |
| S17 | JOIN type not explicitly stated — always use `INNER`, `LEFT`, `RIGHT`, or `FULL` | Medium |
| S18 | Multiple aggregations in separate queries on the same table — combine into one pass | Medium |

---

### Domain 4 — Delta Lake / Databricks

| # | Check | Priority |
|---|---|---|
| D1 | Delta MERGE target table scanned fully due to missing or broad join predicate | Critical |
| D2 | Delta write without schema enforcement (`mergeSchema=True` used carelessly) | Critical |
| D3 | `OPTIMIZE` / `ZORDER BY` not applied on frequently queried hot columns | High |
| D4 | `VACUUM` not called — stale files accumulate, increasing storage cost | High |
| D5 | Delta write missing `partitionBy` for tables expected to exceed 1 GB | High |
| D6 | Overwrite strategy used without idempotency guard or `replaceWhere` | High |
| D7 | Adaptive Query Execution (`spark.sql.adaptive.enabled`) not enabled | Medium |
| D8 | Streaming job missing `checkpointLocation` (no fault tolerance) | Medium |
| D9 | Incremental file ingestion not using Auto Loader (`cloudFiles`) | Medium |
| D10 | Table or column missing `COMMENT` / description metadata | Low |
| D11 | `display()` called in a non-interactive / scheduled notebook context | Low |
| D12 | Delta table constraints (`NOT NULL`, `CHECK`) not defined — no data integrity enforcement | High |
| D13 | Change Data Feed (CDF) not enabled on tables used for CDC / incremental patterns | Medium |
| D14 | `overwrite` mode used on a partitioned Delta table without `replaceWhere` — may corrupt unrelated partitions | Critical |
| D15 | `WHEN NOT MATCHED BY SOURCE` clause missing in full-sync MERGE patterns (stale rows not deleted) | High |
| D16 | Liquid Clustering not considered for tables with multiple high-cardinality filter columns | Low |
| D17 | MERGE condition does not include partition columns — partition pruning skipped, full target scan on every merge | Medium |

---

### Domain 5 — Security

| # | Check | Priority |
|---|---|---|
| SEC1 | User-controlled input passed directly to `spark.sql()` or `execute()` without sanitisation | Critical |
| SEC2 | `eval()` / `exec()` / `os.system()` used with dynamic or user-supplied input | Critical |
| SEC3 | Secrets, tokens, or passwords logged via `print()`, `logging`, or notebook output | Critical |
| SEC4 | Insecure deserialization — `pickle.load()` on untrusted data | High |
| SEC5 | Wildcard permissions in Unity Catalog grants (`GRANT ALL ON *`) | High |
| SEC6 | External URL or hostname constructed from user input (SSRF risk) | High |
| SEC7 | Temporary files written to `/tmp` without cleanup — risk of sensitive data exposure | Medium |
| SEC8 | Stack trace or internal path exposed in notebook output or error message | Medium |
| SEC9 | `dbutils.secrets.get()` result stored in a plain Python variable and printed | Medium |
| SEC10 | Notebook reads from external storage using hardcoded SAS token / access key in code | High |

---

### Domain 6 — Data Quality

| # | Check | Priority |
|---|---|---|
| DQ1 | No null check on critical join keys before performing a join (nulls silently dropped) | Critical |
| DQ2 | No schema validation after reading from external source (CSV, JSON, Parquet) | High |
| DQ3 | Implicit data type cast in assignment or comparison — may silently truncate or overflow | High |
| DQ4 | Duplicate rows not checked or removed before writing to target table | High |
| DQ5 | No row count assertion after a critical transformation (silent data loss risk) | High |
| DQ6 | Date / timestamp parsed without explicit format string (`to_date`, `to_timestamp`) | Medium |
| DQ7 | String columns not trimmed before join or comparison — leading/trailing whitespace mismatch | Medium |
| DQ8 | Aggregation result not validated against expected range or threshold | Medium |
| DQ9 | Missing `.dropna()` / `fillna()` strategy — nulls propagate into output metrics | Medium |
| DQ10 | Column data types not explicitly cast after a join or union (schema drift risk) | Medium |
| DQ11 | No reconciliation check (source row count vs target row count) after load | Low |

---

### Phase 3 — Output Findings Table

After analysis, display a single consolidated numbered table in the following format:

```
| # | Finding | Category | Priority | File Name | Location |
|---|---|---|---|---|---|
| 1 | collect() called on df_sales — may OOM on large datasets | PySpark Performance | Critical | edf_dim_product.py | Line 42, transform() |
| 2 | SELECT * used in sales_query | SQL Optimization | Critical | edf_dim_product.py | Cell 3, Line 7 |
| 3 | Hardcoded table name 'catalog.schema.dim_product' | Python Code Quality | High | edf_dim_product.py | Line 15 |
...
```

- Use **bold** for Critical and High priorities in the chat rendering.
- Sort findings: Critical → High → Medium → Low within each domain.
- Number findings sequentially starting from 1 across all domains.

---

### Phase 4 — Summary & Health Score

After the table, display:

```
──────────────────────────────────────────────────────
 OPTIMIZATION REVIEW SUMMARY
──────────────────────────────────────────────────────
 File(s) reviewed : <filename(s)>
 Total findings   : <N>
   🔴 Critical    : <n>
   🟠 High        : <n>
   🟡 Medium      : <n>
   🟢 Low         : <n>

 Domain Breakdown:
   PySpark Performance    : <n> findings
   Python Code Quality    : <n> findings
   SQL Optimization       : <n> findings
   Delta Lake/Databricks  : <n> findings
   Security               : <n> findings
   Data Quality           : <n> findings

 Health Score      : <score> / 100

 Score Calculation:
   Start at 100
   -15 per Critical finding
   -8  per High finding
   -3  per Medium finding
   -1  per Low finding
   Floor: 0

 ⚡ Top Quick Wins (High Impact, Low Effort):
   #<N1> — <finding title>  [Priority: <level>]
   #<N2> — <finding title>  [Priority: <level>]
   #<N3> — <finding title>  [Priority: <level>]
──────────────────────────────────────────────────────
```

> **Top Quick Wins** are the 3 findings that combine highest priority with lowest fix effort. Always include them even if the user did not ask.

Then **ask the user**:

> Which findings would you like me to fix? Enter the finding numbers (e.g. `1, 3, 5`) or type `all` for all findings. Type `none` to skip fixes.

**Do NOT generate any fix until the user responds.**

---

### Phase 5 — Save CSV Report

Save a CSV file to:
```
Output/CodeOptimization/{FileName}_Optimization_v{n}_{timestamp}.csv
```

Where:
- `{FileName}` = source file name without extension
- `{n}` = auto-incremented version (check existing files in that folder)
- `{timestamp}` = `YYYYMMDD_HHMMSS`

CSV columns:
```
Finding_Number, Finding, Category, Priority, File_Name, Location
```

Notify the user of the saved path.

---

### Phase 6 — Fix Generation (On-Demand Only)

Only execute this phase after the user explicitly selects finding numbers or types `all`.

For each selected finding, output a block in this format:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Finding #<N> — <Short Finding Title>
Category : <Domain>  |  Priority : <Level>
Location : <File Name>, <Location>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BEFORE:
```python / sql
<original code snippet>
```

AFTER:
```python / sql
<fixed code snippet>
```

WHY: <One-sentence explanation of the fix and its benefit>
EFFORT: Low / Medium / High   (Low = <5 min change, Medium = refactor needed, High = architectural change)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Rules for fix generation:**
- Show only the specific lines involved — do not reprint the entire file.
- Preserve the original indentation and style conventions.
- Do not alter logic unrelated to the finding.
- After all selected fixes are shown, ask: *"Would you like to apply any of these fixes to the file?"* — and wait for explicit confirmation before touching the file.
- If the user asks for a **re-review** after fixes are applied, re-run Phase 2–5 against the updated file and compare the new health score to the previous one.

---

## Output Summary

| Output | Location | When |
|---|---|---|
| Findings table (chat) | Chat window | After Phase 2 |
| Health score + summary (chat) | Chat window | After findings table |
| CSV report | `Output/CodeOptimization/` | After Phase 3 |
| Before/After fix blocks (chat) | Chat window | Only when user selects findings |

---

## Example Trigger Prompts

- `optimize code Output/CodeGeneration/edf_dim_product_silver_to_gold.py`
- `check pyspark my_notebook.py`
- `pyspark health check scripts/transform.py`
- `sql optimization queries/sales_report.sql`
- `full review src/pipeline.py`
- `performance audit notebooks/bronze_to_gold.py`
- `security review src/ingestion_pipeline.py`
- `data quality review Output/CodeGeneration/edf_dim_product_silver_to_gold.py`
- `optimize all — pyspark only scripts/transform.py`
- `streaming optimization notebooks/streaming_ingest.py`

---

## Check Domain Reference Card

| Domain | Prefix | Total Checks | Critical | High | Medium | Low |
|---|---|---|---|---|---|---|
| PySpark Performance | P | 35 | 3 | 8 | 14 | 10 |
| Python Code Quality | Q | 21 | 2 | 6 | 7 | 6 |
| SQL Optimization | S | 18 | 2 | 6 | 7 | 3 |
| Delta Lake / Databricks | D | 17 | 3 | 6 | 5 | 3 |
| Security | SEC | 10 | 3 | 4 | 3 | 0 |
| Data Quality | DQ | 11 | 1 | 4 | 5 | 1 |
| **TOTAL** | | **112** | **14** | **34** | **41** | **23** |
