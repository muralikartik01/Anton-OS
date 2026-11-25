# SQL Test Patterns — Parameterized Templates

Each template below is used by the **test-generator** agent to build the test manifest. Placeholders in `{curly_braces}` are replaced with values parsed from `design.md` and `sttm.csv`.

**Conditional generation**: Not every test applies to every Gold table. Each template includes an `Applicability` field that defines when the test should be generated. If the condition is not met, **omit the test entirely** — do not include it in the manifest with a SKIPPED status.

---

## Module 1 — Unit Testing (Transformation & Load Strategy)

### UT-1: Table Exists and Has Data

```sql
SELECT COUNT(*) AS row_count FROM {target_table}
```

| Field | Value |
|-------|-------|
| Expected | `non_zero` |
| Severity | `critical` |
| Applicability | Always — every Gold table must exist and contain data |
| Source | Design overview → Target Table |
| Params | `{target_table}` = fully qualified table from Design `Target Table` field |

---

### UT-2: Column Existence

```sql
DESCRIBE TABLE {target_table}
```

| Field | Value |
|-------|-------|
| Expected | `column_exists:{col1,col2,...,colN}` |
| Severity | `critical` |
| Applicability | Always — every Gold table has columns defined in STTM |
| Source | STTM CSV → all `Target Column*` values |
| Params | `{target_table}` from Design; `{col1,...,colN}` = comma-separated list of every `Target Column*` in STTM CSV |

---

### UT-3: Data Type Conformance

Generate **one test per column** from STTM CSV:

```sql
SELECT typeof({col}) AS actual_type
FROM {target_table}
WHERE {col} IS NOT NULL
LIMIT 1
```

| Field | Value |
|-------|-------|
| Expected | `type_matches:{col:expected_type}` |
| Severity | `warning` |
| Applicability | Always — every column in STTM has a `Target Data Type*` |
| Source | STTM CSV → `Target Column*` + `Target Data Type*` |
| Params | `{col}` = target column name; `{expected_type}` = STTM `Target Data Type*` mapped to Spark types: String→string, Integer→int/bigint, Timestamp→timestamp, Decimal→decimal |
| Note | Agent should batch multiple columns into a single test where practical using: `SELECT typeof(col1), typeof(col2), ... FROM {target_table} LIMIT 1` |

**Spark type mapping reference:**

| STTM Type | Acceptable Spark typeof() Values |
|-----------|----------------------------------|
| String | `string` |
| Integer | `int`, `bigint`, `smallint` |
| Timestamp | `timestamp` |
| Decimal | `decimal(p,s)` |
| Number | `int`, `bigint`, `double`, `float`, `decimal` |
| Boolean | `boolean` |

---

### UT-4: Direct Mapping Correctness

For each column where STTM `Data Transformation Rules*` = `Direct`:

```sql
SELECT COUNT(*) AS mismatch_count
FROM {target_table} t
JOIN {source_table} s
  ON {join_condition}
WHERE t.{target_col} != s.{source_col}
  AND t.{target_col} IS NOT NULL
  AND s.{source_col} IS NOT NULL
```

| Field | Value |
|-------|-------|
| Expected | `zero_rows` |
| Severity | `warning` |
| Applicability | STTM CSV has ≥1 row where `Data Transformation Rules*` = `Direct` |
| Source | STTM CSV → rows with `Data Transformation Rules*` = `Direct`; Design → Join Strategy for source table references |
| Params | `{source_table}` from STTM `Source Table name`; `{source_col}` = STTM `Column Name*`; `{target_col}` = STTM `Target Column*`; `{join_condition}` from Design Join Strategy merge keys |
| Note | Only generate if source table is accessible. If source table cannot be resolved, skip this test for that column. |

---

### UT-5: CAST Transformation Validation

For each column where Design Transformation Catalog `Pattern Category` = `Type Cast`:

```sql
SELECT {target_col}, typeof({target_col}) AS actual_type
FROM {target_table}
WHERE {target_col} IS NOT NULL
LIMIT 5
```

| Field | Value |
|-------|-------|
| Expected | `type_matches:{target_col:expected_type}` |
| Severity | `warning` |
| Applicability | Design Transformation Catalog has ≥1 row with `Pattern Category` = `Type Cast` |
| Source | Design Transformation Catalog → `Type Cast` rows |
| Params | `{target_col}` = Design `Target Column`; `{expected_type}` from STTM `Target Data Type*` |

---

### UT-6: Conditional Logic Spot-Check

For each column where Design Transformation Catalog `Pattern Category` = `Conditional Logic`:

```sql
SELECT DISTINCT {target_col}
FROM {target_table}
WHERE {target_col} IS NOT NULL
```

| Field | Value |
|-------|-------|
| Expected | `matches_set:{expected_values}` |
| Severity | `warning` |
| Applicability | Design Transformation Catalog has ≥1 `Conditional Logic` entry with a finite, enumerable output set (e.g., CASE WHEN with literal THEN values) |
| Source | Design Transformation Catalog → `Conditional Logic` rows → extract expected output values from the CASE WHEN expression |
| Params | `{expected_values}` = comma-separated list of expected output values parsed from the transformation rule (e.g., `Automatic,Manual` from `CASE WHEN ... THEN 'Automatic' ELSE 'Manual' END`) |
| Note | Only generate if the CASE WHEN produces a finite enumerable set of values. Skip for open-ended expressions. |

---

### UT-7: Lookup Enrichment Check

For each column where Design Transformation Catalog `Pattern Category` = `Lookup`:

```sql
SELECT
  COUNT(*) AS total_rows,
  COUNT({target_col}) AS non_null_rows,
  COUNT(*) - COUNT({target_col}) AS null_rows,
  ROUND((COUNT(*) - COUNT({target_col})) * 100.0 / COUNT(*), 2) AS null_pct
FROM {target_table}
```

| Field | Value |
|-------|-------|
| Expected | `non_zero` (checks that the column is at least partially populated) |
| Severity | `warning` |
| Applicability | Design Transformation Catalog has ≥1 row with `Pattern Category` = `Lookup` |
| Source | Design Transformation Catalog → `Lookup` rows |
| Params | `{target_col}` = target column populated via lookup/join |
| Note | LEFT JOIN enrichment columns may legitimately have some NULLs. This test verifies the join produced *some* matches, not 100% fill. |

---

### UT-8: Load Strategy Validation

Generate **one variant** based on the Design `Load Type`. If Load Type is not specified, omit UT-8 entirely.

**For Upsert** (Design `Load Type` = `Upsert`):

```sql
SELECT {merge_keys}, COUNT(*) AS dup_count
FROM {target_table}
GROUP BY {merge_keys}
HAVING COUNT(*) > 1
LIMIT 10
```

| Field | Value |
|-------|-------|
| Expected | `zero_rows` |
| Severity | `critical` |
| Applicability | Design `Load Type` = `Upsert` and merge keys are defined |
| Source | Design → Load Type + Merge Keys |
| Params | `{merge_keys}` = comma-separated merge key columns from Design `Data Load Strategy → Merge Keys` |

**For Append** (Design `Load Type` = `Append`):

```sql
SELECT COUNT(*) AS row_count FROM {target_table}
```

| Field | Value |
|-------|-------|
| Expected | `non_zero` |
| Severity | `warning` |
| Applicability | Design `Load Type` = `Append` |
| Source | Design → Load Type |
| Note | For append, verify data landed. More specific checks require a known prior count. |

**For SCD2** (Design `Load Type` = `SCD2`):

```sql
SELECT COUNT(*) AS open_records
FROM {target_table}
WHERE {end_date_col} IS NULL OR {end_date_col} = '9999-12-31'
```

| Field | Value |
|-------|-------|
| Expected | `non_zero` |
| Severity | `critical` |
| Applicability | Design `Load Type` = `SCD2` and end-date column is identified |
| Source | Design → Load Type; SCD2 end-date column |
| Params | `{end_date_col}` = the SCD2 effective end date column from Design |

---

## Module 2 — Data Quality Testing

### DQ-1: Primary Key Not Null

Generate **one test per PK column** from STTM CSV (where `Primary Key` = `PK`):

```sql
SELECT COUNT(*) AS null_count
FROM {target_table}
WHERE {pk_col} IS NULL
```

| Field | Value |
|-------|-------|
| Expected | `zero_rows` |
| Severity | `critical` |
| Applicability | STTM CSV has ≥1 row where `Primary Key` = `PK` |
| Source | STTM CSV → rows where `Primary Key` column = `PK` |
| Params | `{pk_col}` = STTM `Target Column*` for each PK row |

---

### DQ-2: Primary Key Uniqueness (No Duplicates)

```sql
SELECT {pk_cols}, COUNT(*) AS dup_count
FROM {target_table}
GROUP BY {pk_cols}
HAVING COUNT(*) > 1
LIMIT 10
```

| Field | Value |
|-------|-------|
| Expected | `zero_rows` |
| Severity | `critical` |
| Applicability | STTM CSV has ≥1 row where `Primary Key` = `PK` |
| Source | STTM CSV → all rows where `Primary Key` = `PK` |
| Params | `{pk_cols}` = comma-separated list of all PK target columns |

---

### DQ-3: NOT NULL Constraint Compliance

Generate **one test per NOT NULL column** from STTM CSV (where `Allow Nulls*` = `NOT NULL`):

```sql
SELECT COUNT(*) AS null_count
FROM {target_table}
WHERE {col} IS NULL
```

| Field | Value |
|-------|-------|
| Expected | `zero_rows` |
| Severity | `critical` |
| Applicability | STTM CSV has ≥1 row where `Allow Nulls*` (target, col 17) = `NOT NULL`, excluding columns already covered by DQ-1 |
| Source | STTM CSV → rows where `Allow Nulls*` (target side, column 17) = `NOT NULL` |
| Params | `{col}` = STTM `Target Column*` for each NOT NULL row |
| Note | Agent may batch multiple columns: `WHERE col1 IS NULL OR col2 IS NULL OR ...` to reduce query count |

---

### DQ-4: Valid System & Reporting Unit IDs

```sql
SELECT DISTINCT SourceSystemId, ReportingUnitId
FROM {target_table}
```

| Field | Value |
|-------|-------|
| Expected | `matches_set:{sys_id},{reporting_id}` |
| Severity | `critical` |
| Applicability | Design Audit Columns list concrete (non-`TBD`) values for `SourceSystemId` and `ReportingUnitId` (or your project's equivalent scoping columns) |
| Source | Design → Audit Columns → `SourceSystemId` default, `ReportingUnitId` default |
| Params | `{sys_id}` = expected system ID from Design; `{reporting_id}` = expected reporting unit ID from Design |
| Note | If Design lists values as `TBD`, skip this test and mark as `⚠️ SKIPPED` with note "Expected values TBD" |

---

### DQ-5: Merge Key Not Null

Generate **one test per merge key column** (where STTM `Merge Key` = `Yes`):

```sql
SELECT COUNT(*) AS null_count
FROM {target_table}
WHERE {merge_col} IS NULL
```

| Field | Value |
|-------|-------|
| Expected | `zero_rows` |
| Severity | `critical` |
| Applicability | STTM CSV has ≥1 row where `Merge Key` = `Yes` |
| Source | STTM CSV → rows where `Merge Key` = `Yes` |
| Params | `{merge_col}` = STTM `Target Column*` for each merge key row |

---

### DQ-6: Audit Column Completeness

```sql
SELECT
  COUNT(*) AS total_rows,
  SUM(CASE WHEN MarketCode IS NULL THEN 1 ELSE 0 END) AS null_MarketCode,
  SUM(CASE WHEN SourceSystemId IS NULL THEN 1 ELSE 0 END) AS null_SystemId,
  SUM(CASE WHEN ReportingUnitId IS NULL THEN 1 ELSE 0 END) AS null_ReportingUnitId,
  SUM(CASE WHEN CreatedTimestamp IS NULL THEN 1 ELSE 0 END) AS null_CreatedTimestamp,
  SUM(CASE WHEN CreatedBy IS NULL THEN 1 ELSE 0 END) AS null_CreatedBy,
  SUM(CASE WHEN UpdatedTimestamp IS NULL THEN 1 ELSE 0 END) AS null_UpdatedTimestamp,
  SUM(CASE WHEN UpdatedBy IS NULL THEN 1 ELSE 0 END) AS null_UpdatedBy
FROM {target_table}
```

| Field | Value |
|-------|-------|
| Expected | `zero_rows` (all null counts should be 0) |
| Severity | `critical` |
| Applicability | Always — every Gold table must have its project's mandatory audit columns populated |
| Source | Design → Audit Columns (mandatory audit columns for this project) |
| Note | The pass condition is that **all** `null_*` columns in the result equal 0. The subagent should check each value. Rename the columns above to match your project's actual audit-column convention. |

---

### DQ-7: Custom DQ Rules

No fixed SQL template — the agent inspects the `Comments` column in both STTM CSV and the Design `Transformation Catalog` for any explicit DQ expectations (e.g., "values must be positive", "date must be ≥ 2020-01-01").

For each discovered rule, the agent constructs an appropriate SQL validation query. Example:

```sql
-- If STTM Comments says "must be positive"
SELECT COUNT(*) AS violation_count
FROM {target_table}
WHERE {col} <= 0

-- If Design says "date must be ≥ 2020-01-01"
SELECT COUNT(*) AS violation_count
FROM {target_table}
WHERE {col} < '2020-01-01'
```

| Field | Value |
|-------|-------|
| Expected | `zero_rows` |
| Severity | `warning` |
| Applicability | Design or STTM `Comments` columns contain explicit, testable DQ rules. If none found, omit DQ-7 entirely |
| Source | STTM CSV `Comments` columns + Design `Transformation Catalog → Comments` |
| Note | Only generate if explicit, testable DQ rules are found. Do not invent rules. If no custom DQ rules are found, omit DQ-7 entirely. |

---

## Module 3 — Performance Testing

### PT-1: Partition Columns Exist

```sql
DESCRIBE DETAIL {target_table}
```

| Field | Value |
|-------|-------|
| Expected | `column_exists:partitionColumns` — then verify the `partitionColumns` value contains `{expected_partitions}` |
| Severity | `warning` |
| Applicability | Design Partitioning Strategy specifies partition columns |
| Source | Design → Partitioning Strategy → `Partition Columns` |
| Params | `{expected_partitions}` = partition columns from Design (e.g., `SourceSystemId,ReportingUnitId`) |
| Note | `DESCRIBE DETAIL` returns a single row with a `partitionColumns` array. The subagent should parse this array and compare against expected columns. |

---

### PT-2: Partition Pruning Validation

```sql
EXPLAIN SELECT * FROM {target_table} WHERE {partition_col} = {sample_value}
```

| Field | Value |
|-------|-------|
| Expected | `non_zero` (verify the plan output contains `PartitionFilters` or `partition pruning`) |
| Severity | `warning` |
| Applicability | Design Partitioning Strategy specifies partition columns |
| Source | Design → Partitioning Strategy → `Partition Columns` |
| Params | `{partition_col}` = first partition column from Design; `{sample_value}` from Design expected values (e.g., SourceSystemId default) |
| Note | The subagent checks EXPLAIN output for evidence of partition pruning. If the plan contains `PartitionFilters` or `PushedFilters` referencing the partition column, mark GREEN. |

---

### PT-3: ZORDER Validation

```sql
DESCRIBE DETAIL {target_table}
```

| Field | Value |
|-------|-------|
| Expected | `non_zero` (verify output contains ZORDER metadata if applicable) |
| Severity | `warning` |
| Applicability | Design Partitioning Strategy specifies ZORDER columns. If no ZORDER specified, omit PT-3 entirely |
| Source | Design → Partitioning Strategy (ZORDER BY clause if specified) |
| Params | `{expected_zorder_cols}` from Design (e.g., `OrderId,CustomerId,SalesOrganizationCode`) |
| Note | ZORDER is an optimization hint — Delta Lake does not always expose it in `DESCRIBE DETAIL`. If Design does not specify ZORDER, skip this test entirely. If ZORDER is specified but cannot be verified via metadata, mark as `⚠️ SKIPPED` with note "ZORDER not verifiable via DESCRIBE DETAIL". |

---

## Template Variable Reference

All placeholders used across templates and where to source them:

| Placeholder | Source |
|-------------|--------|
| `{target_table}` | Design → `Target Table` (e.g., `catalog.schema.TableName`) |
| `{col}` / `{target_col}` | STTM CSV → `Target Column*` |
| `{source_table}` | STTM CSV → `Source Table name` |
| `{source_col}` | STTM CSV → `Column Name*` |
| `{pk_col}` / `{pk_cols}` | STTM CSV → rows where `Primary Key` = `PK` → `Target Column*` |
| `{merge_keys}` | Design → `Data Load Strategy → Merge Keys` |
| `{merge_col}` | STTM CSV → rows where `Merge Key` = `Yes` → `Target Column*` |
| `{expected_type}` | STTM CSV → `Target Data Type*` |
| `{expected_values}` | Design Transformation Catalog → parsed from CASE WHEN expressions |
| `{expected_partitions}` | Design → `Partitioning Strategy → Partition Columns` |
| `{partition_col}` | First partition column from Design |
| `{sample_value}` | Design → audit column defaults or partition column expected value |
| `{sys_id}` | Design → Audit Columns → SourceSystemId default |
| `{reporting_id}` | Design → Audit Columns → ReportingUnitId default |
| `{join_condition}` | Design → Join Strategy → ON conditions |
| `{end_date_col}` | Design → SCD2 effective end date column |
| `{expected_zorder_cols}` | Design → Partitioning Strategy → ZORDER BY |
