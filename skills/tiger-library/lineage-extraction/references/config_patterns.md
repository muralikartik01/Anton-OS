# Lineage Extraction Patterns Reference

This document provides extraction patterns and examples for the lineage-extraction skill.

Last Updated: 2026-07-09

---

## Source Table Type Classification Rules

### Unity Catalog Sources

| Condition | Source_Table_Type | Example |
|-----------|-------------------|---------|
| Catalog = `{silver_catalog}` AND Schema contains `bronze` | **Bronze** | `{silver_catalog}.fdn_customer_bronze_view.tbl_bronze_customer_staging` |
| Catalog = `{silver_catalog}` AND Schema does NOT contain `bronze` or `gold` | **Silver** | `{silver_catalog}.fdn_material_view.xcfmaterialcore` |
| Catalog ≠ `{silver_catalog}` AND Schema contains `gold` | **Gold** | `{gold_catalog}.{gold_schema}.location` |
| Catalog contains `mosaic` AND Schema contains `gold` | **Gold** | `{gold_catalog}.{finance_gold_schema}.customermapping` |

### Non-Unity Catalog Sources

| Pattern | Source_Table_Type | Example |
|---------|-------------------|---------|
| ADLS path starting with `abfss://` | **Parquet** | `abfss://{your_storage_container}@{your_storage_account}.dfs.core.windows.net/OUTPUT/Master/DimensionDate/*` |
| Manual / External / Reference table | **Reference** | Manual input files, lookup tables |

---

## System ID Extraction Patterns

### From Query Parameter (Generic Notebook)

When `audit_parameters.query` field contains SQL:

```sql
-- Pattern 1: Simple equality
WHERE SourceSystemId = 1961 AND ReportingUnitId = 107242

-- Pattern 2: IN clause  
WHERE SourceSystemId IN (1961, 1547) AND ReportingUnitId IN (107242, 100046)

-- Pattern 3: Mixed with other filters
WHERE SourceSystemId = 1961 
  AND ReportingUnitId = 107242
  AND StatusCode = 'ACTIVE'
  AND EffectiveDate >= '2024-01-01'
```

**Extraction Logic**:
- Parse WHERE clause for `SourceSystemId =` or `SourceSystemId IN`
- Parse WHERE clause for `ReportingUnitId =` or `ReportingUnitId IN`
- Extract values (may be multiple separated by commas)
- Store other conditions in `Filters_Used[]` array

### From Dedicated Notebook

When `audit_parameters.query` is NULL, read notebook source code:

```python
# Pattern 1: DataFrame filter
df = spark.table(source_table).filter(
    (col("SourceSystemId") == 1961) &
    (col("ReportingUnitId") == 107242)
)

# Pattern 2: SQL string in notebook
query = """
    SELECT * FROM {source_table}
    WHERE SourceSystemId = 1961
    AND ReportingUnitId = 107242
"""

# Pattern 3: Widget parameters
system_id = dbutils.widgets.get("SourceSystemId")  # Extract from widget default
```

### Fallback Rules

1. **No explicit filter found** → Inherit target table's system/reporting unit IDs
2. **Parquet source** → Use "N/A" (acceptable)
3. **Bronze staging table** → Use "N/A" (acceptable)
4. **Manual reference table** → Use "N/A" (acceptable)

---

## Schedule Extraction Patterns

### From job_schedule Table

```sql
SELECT 
  ScheduleFrequency, 
  ScheduleDay, 
  ScheduleHour, 
  ScheduleMinute
FROM {audit_catalog}.{audit_schema}.job_schedule
WHERE PL_Name = 'PL_Example_BU1_US_Product'
```

**Mapping to schedule object**:

| ScheduleFrequency | schedule.frequency | Example schedule.day | Example schedule.hour/minute |
|-------------------|-------------------|----------------------|------------------------------|
| D | D (Daily) | "" (empty) | "12" / "30" |
| W | W (Weekly) | "Monday" | "12" / "30" |
| M | M (Monthly) | "1" (day of month) | "12" / "30" |
| FP | FP (FinancialPeriod) | "4" (day in period) | "11" / "30" |
| FILEWATCH | FILEWATCH | "Thursday" | "19" / "0" |

---

## Market Hierarchy Patterns

**CRITICAL: Pipeline is the unique identifier**:
- If a Gold table is loaded by multiple pipelines, create **separate JSON entries** for each pipeline
- Example: `{gold_schema}.transportlaneloadmetrics` loaded by 2 pipelines → 2 entries in JSON

### Market Code Mapping

**MarketName Field**:
- Contains **country codes**: US, CA, MX, BR, CN, AU, etc.
- Do NOT use sector names (BU1, BU2, BU_ALT1) as market codes
- Extract country code directly from `MarketName` field

| MarketName in audit_parameters | market_code | market_name | business_unit_name |
|--------------------------------|-------------|-------------|--------------------|
| US | US | US - United States | BU1 or BU2 |
| Global | Global | Global | BU1 (default) |
| MX | MX | MX - Mexico | BU3 |
| CA | CA | CA - Canada | BU1 |
| BR | BR | BR - Brazil | BU3 |
| CN | CN | CN - China | BU5 |
| AU | AU | AU - Australia | BU5 |

**Sector (Business Unit) Determination**:
- Extract from `SectorName` field in audit_parameters
- **Valid sectors (only 6)**: **BU1, BU2, BU3, BU4, BU5, BU6**
- **Sector mapping rules** (when SectorName doesn't match valid list):
  - **BU_ALT1** (Example Manufacturing Unit) → **BU3**
  - **BU_ALT2** (Example Frontline Unit) → **BU2**
  - **Global** / **NA** / **your organization** → Infer from country code:
    - US, CA → **BU1** or **BU2** (check context)
    - MX, BR, AR, CL, CO → **BU3**
    - CN, AU, JP, TH, VN → **BU5**
    - UK, DE, FR, PL, ES → **BU6**
    - ZA, EG, KE, IN → **BU4**
  - If ambiguous → default to **BU1** with market="Global"

**Business Unit → Market Rollup**:
- BU1 markets: US, CA
- BU2 markets: US, CA
- BU3 markets: MX, BR, AR, CL, CO
- BU4 markets: ZA, EG, KE, IN
- BU5 markets: CN, AU, JP, TH, VN
- BU6 markets: UK, DE, FR, PL, ES

---

## Known Edge Cases

### 1. Multiple Source Catalog/Schema/Table Sets

Some pipelines use `source_catalog_name1` through `source_catalog_name7` in audit_parameters:

```sql
get_json_object(ParameterValue, '$.source_catalog_name1') AS source_catalog_name1,
get_json_object(ParameterValue, '$.source_schema_name1') AS source_schema_name1,
get_json_object(ParameterValue, '$.source_table_name1') AS source_table_name1,
-- ... up to source_catalog_name7
```

**Extraction**: Query all 8 sets (0-7), filter out NULLs, build Sources[] array.

### 2. Parquet Sources from ADLS

When source is not a UC table but an ADLS path:

```json
{
  "Source_Table_Type": "Parquet",
  "Source_Path": "abfss://{your_storage_container}@{your_storage_account}.dfs.core.windows.net/OUTPUT/Master/DimensionDate/*",
  "Filters_Used": [],
  "Join_Type": "N/A",
  "SourceSystemId": "N/A",
  "ReportingUnitId": "N/A"
}
```

No `Table_Name`, `Table_ShortName`, `Catalog`, or `Schema` fields.

### 3. Bronze Staging Tables with No System IDs

Program Bronze staging tables (`tbl_bronze_*`) sourced from external files often have no system ID filters.

**Pattern**:
```json
{
  "Source_Table_Type": "Bronze",
  "Table_Name": "{silver_catalog}.fdn_customer_bronze_view.tbl_bronze_customer_staging",
  "SourceSystemId": "N/A",
  "ReportingUnitId": "N/A",
  "Filters_Used": []
}
```

This is **acceptable** — Bronze layer acts as staging, system IDs applied at transformation level.

### 4. Gold-to-Gold Cross-References

Some Gold tables source from other Gold tables:

```json
{
  "Source_Table_Type": "Gold",
  "Table_Name": "{gold_catalog}.{gold_schema}.location",
  "SourceSystemId": "N/A",
  "ReportingUnitId": "107242",
  "Filters_Used": ["XTNMarketCode = 'US'"]
}
```

System ID may be "N/A" if not explicitly filtered (inherits from consuming table's logic).

---

## Notebook Path Patterns

### Common Notebook Paths

| Pattern | Usage |
|---------|-------|
| `/Workspace/{your_workspace_path}/Common/Utility/NB_Common_GenericDataIngestor` | Generic notebook using query parameter |
| `/Workspace/{your_workspace_path}/Common/Utility/NB_Manual_Example_Ingest` | Manual file ingestion |
| `/Workspace/{your_workspace_path}/PTS/BU1/US/NB_Example_BU1_US_<TableName>` | Dedicated notebook per table |

**Generic Notebook Detection**:
- If `nb_path` contains "GenericDataIngestor" → Must have `query` parameter with SQL
- If `nb_path` contains "Manual" → Likely Parquet or external source
- Otherwise → Read notebook source code for transformation logic

---

## Load Type Patterns

| load_type Value | Description | Typical Usage |
|-----------------|-------------|---------------|
| upsert | Merge with WHEN MATCHED THEN UPDATE | Dimension tables with updates |
| append | INSERT only, no updates | Fact tables, immutable logs |
| overwrite_partition | Overwrite specific partition(s) | Partitioned fact tables |
| overwrite | Full table overwrite | Small dimensions, complete refreshes |
| scd2 | Slowly Changing Dimension Type 2 | Dimension with history tracking |
| delete_insert | DELETE + INSERT pattern | Replace subset of data |
| parquet_overwrite | Write to Parquet in ADLS | Staging layer outputs |

---

## Join Type Extraction (Future Enhancement)

Currently `Join_Type` is set to "N/A" or not populated.

Future: Parse notebook SQL to detect:
- LEFT JOIN
- INNER JOIN
- RIGHT JOIN
- FULL OUTER JOIN
- CROSS JOIN

This requires notebook source code parsing beyond current scope.

---

## Filters_Used Array Format

Always store as array of individual filter conditions:

```json
"Filters_Used": [
  "SourceSystemId = 1961",
  "ReportingUnitId = 107242",
  "StatusCode = 'ACTIVE'",
  "EffectiveDate >= '2024-01-01'"
]
```

NOT as single concatenated string:
```json
"Filters_Used": "SourceSystemId = 1961 AND ReportingUnitId = 107242"  // ❌ Wrong
```

