# Lineage Extraction Queries

Reference SQL queries used by the lineage-extraction skill. All queries run via Databricks MCP server against production audit tables.

---

## Query 1 — Audit Parameters

Extracts pipeline configuration, target table, all source tables (primary + suffixes 2–12), per-source system/reporting unit IDs, load type, DQ config, and hierarchy metadata from `audit_parameters`.

Replace `<pipeline_name>` with the actual `PL_Name` value before executing.

```sql
SELECT
  PL_Name,
  get_json_object(ParameterValue, '$.target_catalog_name')           AS target_catalog_name,
  get_json_object(ParameterValue, '$.target_schema_name')            AS target_schema_name,
  get_json_object(ParameterValue, '$.target_table_name')             AS target_table_name,
  get_json_object(ParameterValue, '$.source_catalog_name')           AS source_catalog_name,
  get_json_object(ParameterValue, '$.source_schema_name')            AS source_schema_name,
  get_json_object(ParameterValue, '$.source_table_name')             AS source_table_name,
  get_json_object(ParameterValue, '$.source_SourceSystemId')          AS source_SourceSystemId,
  get_json_object(ParameterValue, '$.source_ReportingUnitId')   AS source_ReportingUnitId,
  get_json_object(ParameterValue, '$.source_catalog_name2')          AS source_catalog_name2,
  get_json_object(ParameterValue, '$.source_schema_name2')           AS source_schema_name2,
  get_json_object(ParameterValue, '$.source_table_name2')            AS source_table_name2,
  get_json_object(ParameterValue, '$.source_SourceSystemId2')         AS source_SourceSystemId2,
  get_json_object(ParameterValue, '$.source_ReportingUnitId2')  AS source_ReportingUnitId2,
  get_json_object(ParameterValue, '$.source_catalog_name3')          AS source_catalog_name3,
  get_json_object(ParameterValue, '$.source_schema_name3')           AS source_schema_name3,
  get_json_object(ParameterValue, '$.source_table_name3')            AS source_table_name3,
  get_json_object(ParameterValue, '$.source_SourceSystemId3')         AS source_SourceSystemId3,
  get_json_object(ParameterValue, '$.source_ReportingUnitId3')  AS source_ReportingUnitId3,
  get_json_object(ParameterValue, '$.source_catalog_name4')          AS source_catalog_name4,
  get_json_object(ParameterValue, '$.source_schema_name4')           AS source_schema_name4,
  get_json_object(ParameterValue, '$.source_table_name4')            AS source_table_name4,
  get_json_object(ParameterValue, '$.source_SourceSystemId4')         AS source_SourceSystemId4,
  get_json_object(ParameterValue, '$.source_ReportingUnitId4')  AS source_ReportingUnitId4,
  get_json_object(ParameterValue, '$.source_catalog_name5')          AS source_catalog_name5,
  get_json_object(ParameterValue, '$.source_schema_name5')           AS source_schema_name5,
  get_json_object(ParameterValue, '$.source_table_name5')            AS source_table_name5,
  get_json_object(ParameterValue, '$.source_SourceSystemId5')         AS source_SourceSystemId5,
  get_json_object(ParameterValue, '$.source_ReportingUnitId5')  AS source_ReportingUnitId5,
  get_json_object(ParameterValue, '$.source_catalog_name6')          AS source_catalog_name6,
  get_json_object(ParameterValue, '$.source_schema_name6')           AS source_schema_name6,
  get_json_object(ParameterValue, '$.source_table_name6')            AS source_table_name6,
  get_json_object(ParameterValue, '$.source_SourceSystemId6')         AS source_SourceSystemId6,
  get_json_object(ParameterValue, '$.source_ReportingUnitId6')  AS source_ReportingUnitId6,
  get_json_object(ParameterValue, '$.source_catalog_name7')          AS source_catalog_name7,
  get_json_object(ParameterValue, '$.source_schema_name7')           AS source_schema_name7,
  get_json_object(ParameterValue, '$.source_table_name7')            AS source_table_name7,
  get_json_object(ParameterValue, '$.source_SourceSystemId7')         AS source_SourceSystemId7,
  get_json_object(ParameterValue, '$.source_ReportingUnitId7')  AS source_ReportingUnitId7,
  get_json_object(ParameterValue, '$.source_catalog_name8')          AS source_catalog_name8,
  get_json_object(ParameterValue, '$.source_schema_name8')           AS source_schema_name8,
  get_json_object(ParameterValue, '$.source_table_name8')            AS source_table_name8,
  get_json_object(ParameterValue, '$.source_SourceSystemId8')         AS source_SourceSystemId8,
  get_json_object(ParameterValue, '$.source_ReportingUnitId8')  AS source_ReportingUnitId8,
  get_json_object(ParameterValue, '$.source_catalog_name9')          AS source_catalog_name9,
  get_json_object(ParameterValue, '$.source_schema_name9')           AS source_schema_name9,
  get_json_object(ParameterValue, '$.source_table_name9')            AS source_table_name9,
  get_json_object(ParameterValue, '$.source_SourceSystemId9')         AS source_SourceSystemId9,
  get_json_object(ParameterValue, '$.source_ReportingUnitId9')  AS source_ReportingUnitId9,
  get_json_object(ParameterValue, '$.source_catalog_name10')         AS source_catalog_name10,
  get_json_object(ParameterValue, '$.source_schema_name10')          AS source_schema_name10,
  get_json_object(ParameterValue, '$.source_table_name10')           AS source_table_name10,
  get_json_object(ParameterValue, '$.source_SourceSystemId10')        AS source_SourceSystemId10,
  get_json_object(ParameterValue, '$.source_ReportingUnitId10') AS source_ReportingUnitId10,
  get_json_object(ParameterValue, '$.source_catalog_name11')         AS source_catalog_name11,
  get_json_object(ParameterValue, '$.source_schema_name11')          AS source_schema_name11,
  get_json_object(ParameterValue, '$.source_table_name11')           AS source_table_name11,
  get_json_object(ParameterValue, '$.source_SourceSystemId11')        AS source_SourceSystemId11,
  get_json_object(ParameterValue, '$.source_ReportingUnitId11') AS source_ReportingUnitId11,
  get_json_object(ParameterValue, '$.source_catalog_name12')         AS source_catalog_name12,
  get_json_object(ParameterValue, '$.source_schema_name12')          AS source_schema_name12,
  get_json_object(ParameterValue, '$.source_table_name12')           AS source_table_name12,
  get_json_object(ParameterValue, '$.source_SourceSystemId12')        AS source_SourceSystemId12,
  get_json_object(ParameterValue, '$.source_ReportingUnitId12') AS source_ReportingUnitId12,
  get_json_object(ParameterValue, '$.type_of_load')                  AS type_of_load,
  get_json_object(ParameterValue, '$.dq_dataset_name')               AS dq_dataset_name,
  get_json_object(ParameterValue, '$.dq_flag')                       AS dq_flag,
  get_json_object(ParameterValue, '$.nb_path')                       AS nb_path,
  get_json_object(ParameterValue, '$.query')                         AS query,
  get_json_object(ParameterValue, '$.SectorName')                    AS SectorName,
  get_json_object(ParameterValue, '$.MarketName')                    AS MarketName,
  get_json_object(ParameterValue, '$.table_type')                    AS table_type,
  get_json_object(ParameterValue, '$.module')                        AS module
FROM {audit_catalog}.{audit_schema}.audit_parameters
WHERE PL_Name = '<pipeline_name>'
```

**Source table iteration rule**: After executing, iterate over slots primary (no suffix) through 12. Stop when `source_catalog_name<N>` and `source_table_name<N>` are both NULL or empty. Map each slot's `source_SourceSystemId<N>` and `source_ReportingUnitId<N>` to that slot's source entry.

---

## Query 2 — Job Schedule

Retrieves workflow schedule metadata for a given pipeline.

Replace `<pipeline_name>` with the actual `PL_Name` value before executing.

```sql
SELECT
  PL_Name,
  WorkspaceEnvironment,
  ScheduleFrequency,
  ScheduleDay,
  ScheduleHour,
  ScheduleMinute,
  WorkflowName,
  ActiveFlag
FROM {audit_catalog}.{audit_schema}.job_schedule
WHERE PL_Name = '<pipeline_name>'
  AND ActiveFlag = 'Y'
  AND WorkspaceEnvironment = 'SPOT'
```

---

## Query 3 — System ID Master

Looks up human-readable system names for all unique `SourceSystemId` values discovered during a lineage extraction run.

Replace `<unique_system_ids_from_lineage>` with a comma-separated list of integer IDs (e.g., `1005, 1012, 1961`) before executing.

```sql
SELECT
  SourceSystemId,
  SystemName,
  SystemType,
  DataClassification
FROM {silver_catalog}.fdn_common_view.xtn_system_master
WHERE SourceSystemId IN (<unique_system_ids_from_lineage>)
```

---

## Query 4 — EDF Data Asset Details (System ID Validation)

Validates `SourceSystemId` and `ReportingUnitId` for **all Silver sources** by looking up the authoritative values from `edfdataassetdetails`. Run once per pipeline as a **single batched query** covering all Silver source tables — even when IDs appear populated, as existing values may be incorrect.

Fix code is generated (Step 3a-2) whenever the returned values differ from the current values, or when current values are empty/N/A.

Collect all `Table_ShortName` values from Silver sources in the pipeline, lowercase them, and pass as a single `IN` list:

```sql
-- Single batched query for all Silver sources in a pipeline
SELECT
  SilverTableName,
  DataFoundationSystemID,
  DataFoundationReportingUnitID
FROM {audit_catalog}.{audit_schema}.edfdataassetdetails
WHERE LOWER(SilverTableName) IN (
  '<table_shortname_1>',
  '<table_shortname_2>',
  '<table_shortname_3>'  -- all Silver Table_ShortName values, lowercased
)
```

After executing, join results back to source entries by matching `LOWER(SilverTableName)` against `LOWER(Table_ShortName)`.

> **Fix code generation**: See **Step 3a-2** in `SKILL.md` for the full upsert code templates — both slot-based (system ID keys only) and query-based (all five source slot fields). Do NOT generate fix code from this file; `queries.md` contains SQL only.

**Result mapping** (from `edfdataassetdetails` query result to source entry):
- `DataFoundationSystemID` → `SourceSystemId`
- `DataFoundationReportingUnitID` → `ReportingUnitId`

**Match → no action**: If returned values match current values, confirm correct and skip fix code generation.

**Mismatch or empty → generate fix code**: If returned values differ from current (or current is empty/N/A), update in-memory value and generate fix code block.

**Multiple rows**: Use the first non-null result. Log a warning if more than one distinct ID pair is returned — it may indicate a multi-system source requiring manual review.

**No rows returned**: Log `[WARN] No EDF asset record found for Silver table '<table_shortname>'` — keep existing value; flag for user review.
