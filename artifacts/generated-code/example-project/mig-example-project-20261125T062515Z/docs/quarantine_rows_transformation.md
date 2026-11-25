# Transformation: silver.quarantine_rows

## 1. Overview
- Notebook: `silver/quarantine_rows.py` (`artifacts/generated-code/example-project/mig-example-project-20261125T062515Z/silver/quarantine_rows.py`)
- Layer: Silver
- Target: `{silver_catalog}.{silver_schema}.quarantine_rows`
- Purpose (header cell): creates the Silver quarantine table (rows are inserted by the other Silver notebooks)

## 2. Source tables
- N/A (DDL only)

## 3. Target load config
- Strategy: create-only (no data written)
- Key columns: `source_table,record_key,reason,_run_id`
- Quarantine table: N/A
- Statements executed in order: ddl

## 4. Filters
N/A

## 5. Join logic
N/A

## 6. Transformation logic
N/A (create-only notebook: the DDL defines `source_table, record_key, reason, row_json, _run_id, _ingested_at, _source_table`; no SELECT)

---
Mapping rows: silver.quarantine_rows.* — columns: no mapping row (quarantine_rows columns are `no_mapping` rows in the mapping)
Generated from: `silver/quarantine_rows.py`
