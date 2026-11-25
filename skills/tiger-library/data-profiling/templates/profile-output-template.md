# Data Profile: <catalog.schema.table>

**Run Date:** <MM/DD/YYYY>  
**Output Path:** `Output/DataProfiling/<TableName>_<MMDDYYYY>.md`

## Level 1 — Quick Profile

| Metric | Value |
|---|---:|
| Row Count | |
| Column Count | |
| Duplicate Row Count | |

### Null % by Column (Top 15)

| Column | Null Count | Null % |
|---|---:|---:|

### Distinct Count by Column (Top 15)

| Column | Distinct Count |
|---|---:|

## Level 2 — Distribution & Cardinality

### Numeric Columns

| Column | Min | Max | Avg | Stddev | P50 | P90 | P95 | P99 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|

### String Columns

| Column | Min Length | Max Length | Avg Length |
|---|---:|---:|---:|

### Top Values (per key string column, Top 10 each)

| Column | Value | Count |
|---|---|---:|

## Level 3 — Temporal & Freshness

### Temporal Coverage

| Column | Min Date | Max Date | Coverage Days |
|---|---|---|---:|

### Daily Volume (Last 30 Days)

| Date | Row Count |
|---|---:|

## Level 4 — Quality Rules

| Check | Result |
|---|---|
| Negative Value Counts | |
| Blank String Counts | |
| Potential Key Candidates | |
| Duplicate Row Sample Count | |

## Observations / Anomalies

- [Severity: High|Medium|Low] <finding 1>
