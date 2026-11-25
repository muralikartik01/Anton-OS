# Lineage Extraction — Accumulated Learnings

This file is updated by the agent after each successful run. It captures
patterns, edge cases, and fixes discovered during extraction so future
runs are faster and more accurate.

**Format**: Append new entries at the bottom. Never delete past entries —
they form an audit trail of improvements.

Last Updated: 2026-07-09

---

## Run History Summary

| Run | Date | SubProject | Tables Processed | Checks Passed | Key Learning |
|-----|------|------------|------------------|---------------|--------------|
| 1 | 2026-07-09 | PTS | 0 | N/A | Initial skill setup - no runs yet |

---

## Edge Cases Discovered

### 1. Parquet Sources from ADLS (2026-07-09)
**Problem**: Some Gold tables ingest directly from ADLS Parquet files, not Unity Catalog tables.
**Pattern**: `Source_Path` = `abfss://{your_storage_container}@{your_storage_account}.dfs.core.windows.net/OUTPUT/Master/...`
**Fix**: 
- Set `Source_Table_Type = "Parquet"`
- Omit `Table_Name`, `Table_ShortName`, `Catalog`, `Schema` fields
- Set `SourceSystemId = "N/A"` and `ReportingUnitId = "N/A"`
- This is **acceptable** for file-based sources
**Added to**: config_patterns.md

### 2. Bronze Staging Tables with No System IDs (2026-07-09)
**Problem**: Program Bronze staging tables (`tbl_bronze_*`) often have no system ID filters because they're populated from external files.
**Example**: `{silver_catalog}.fdn_customer_bronze_view.tbl_bronze_customer_staging`
**Fix**: 
- Set `SourceSystemId = "N/A"` and `ReportingUnitId = "N/A"`
- This is **acceptable** — system IDs are applied at Silver→Gold transformation level
**Status**: Documented as acceptable pattern

### 3. Multiple Source Catalog/Schema/Table Sets (2026-07-09)
**Problem**: Some pipelines use up to 8 source table sets (source_catalog_name0-7) in audit_parameters.
**Fix**: Query all 8 sets from ParameterValue JSON, filter out NULLs, build complete Sources[] array.
**Code Pattern**:
```sql
get_json_object(ParameterValue, '$.source_catalog_name') AS source_catalog_name,
get_json_object(ParameterValue, '$.source_catalog_name1') AS source_catalog_name1,
-- ... through source_catalog_name7
```

### 4. Gold-to-Gold Cross-References (2026-07-09)
**Problem**: Some Gold tables source from other Gold tables (e.g., `{gold_schema}.product` sources from `{gold_schema}.location`).
**Pattern**: `Source_Table_Type = "Gold"`
**Fix**: 
- This is valid — Gold tables can depend on other Gold tables
- System ID may be "N/A" if not explicitly filtered
- Ensure lineage graph can handle Gold→Gold edges

---

## Source Type Classification Rules (Confirmed)

| Condition | Source_Table_Type | confirmed_date |
|-----------|-------------------|----------------|
| Catalog = `{silver_catalog}` AND Schema contains `bronze` | **Bronze** | 2026-07-09 |
| Catalog = `{silver_catalog}` AND Schema NOT contains `bronze` or `gold` | **Silver** | 2026-07-09 |
| Catalog ≠ `{silver_catalog}` AND Schema contains `gold` | **Gold** | 2026-07-09 |
| Catalog contains `mosaic` AND Schema contains `gold` | **Gold** | 2026-07-09 |
| Source is ADLS path (`abfss://`) | **Parquet** | 2026-07-09 |

---

## System ID Extraction Rules (Confirmed)

### Priority Order

1. **From query parameter** (if generic notebook): Parse SQL WHERE clause
2. **From dedicated notebook**: Parse DataFrame filters and SQL strings in notebook code
3. **Inherit from target table**: Use target's system/reporting unit IDs
4. **Fallback to "N/A"**: For Parquet, Bronze staging, manual sources

### Regex Patterns

| Field | Regex | Example | Notes |
|-------|-------|---------|-------|
| SourceSystemId | `SourceSystemId\s*=\s*['\"]?(\d+)` | `SourceSystemId = 1961` | Case-insensitive, optional quotes |
| ReportingUnitId | `ReportingUnitId\s*=\s*['\"]?(\d+)` | `ReportingUnitId='107242'` | May have quotes |
| IN clause | `SourceSystemId\s+IN\s*\(([^)]+)\)` | `SourceSystemId IN (1961, 1547)` | Extract comma-separated list |

---

## Market Hierarchy Mappings (Confirmed)

**CRITICAL RULE**: Pipeline is the unique identifier. If a Gold table is loaded by multiple pipelines, create separate JSON entries for each pipeline.

### Valid Sectors (Only 6)

**Sectors**: BU1, BU2, BU3, BU4, BU5, BU6

**Sector Mapping Rules** (when SectorName doesn't match):
- **BU_ALT1** (Example Manufacturing Unit) → **BU3**
- **BU_ALT2** (Example Frontline Unit) → **BU2**
- **Global** / **NA** → Infer from country code (see below)

### Market Code → Full Name

**Market is country code**, not sector name.

| market_code | market_name | business_unit_name | Confirmed By |
|-------------|-------------|--------------------|--------------|
| US | US - United States | BU1 or BU2 | Schema (2026-07-09) |
| CA | CA - Canada | BU1 | Schema (2026-07-09) |
| MX | MX - Mexico | BU3 | Schema (2026-07-09) |
| BR | BR - Brazil | BU3 | Schema (2026-07-09) |
| CN | CN - China | BU5 | Schema (2026-07-09) |
| AU | AU - Australia | BU5 | Schema (2026-07-09) |
| Global | Global | BU1 (default) | Schema (2026-07-09) |

### Country Code → Sector Mapping (When SectorName is ambiguous)

| Country Codes | Sector |
|---------------|--------|
| US, CA | BU1 or BU2 (check context) |
| MX, BR, AR, CL, CO | BU3 |
| CN, AU, JP, TH, VN | BU5 |
| UK, DE, FR, PL, ES | BU6 |
| ZA, EG, KE, IN | BU4 |
| MX | MX - Mexico | BU3 | Schema (2026-07-09) |
| CA | CA - Canada | BU1 | To be confirmed |
| BR | BR - Brazil | BU3 | To be confirmed |

### Sector Values

Confirmed valid values for `SectorName`:
- BU1 (Business Unit 1 (example))
- BU2 (Business Unit 2 (example))
- BU3 (Latin America)
- BU_ALT2 (Frito-Lay US)
- BU4 (Africa, Middle East, South Asia)
- BU5 (Asia Pacific)
- BU6 (Europe)
- Global

---

## Schedule Frequency Mappings (Confirmed)

| ScheduleFrequency | schedule.frequency | Example day | Example hour/minute |
|-------------------|-------------------|-------------|---------------------|
| D | D (Daily) | "" | "12" / "30" |
| W | W (Weekly) | "Monday" | "12" / "30" |
| M | M (Monthly) | "1" | "12" / "30" |
| FP | FP (FinancialPeriod) | "4" | "11" / "30" |
| FILEWATCH | FILEWATCH | "Thursday" | "19" / "0" |

---

## Project Name Mappings (Confirmed)

| PL_Name Prefix | Project | SubProject | Confirmed By |
|----------------|---------|------------|--------------|
| PL_PTS_ | Program | PTS | Schema (2026-07-09) |
| PL_CBV_ | Program | CBV | Schema (2026-07-09) |
| PL_PostCadDo_ | Program | PostCadDo | Schema (2026-07-09) |
| PL_PreCadDo_ | Program | PreCadDo | Schema (2026-07-09) |

---

## Load Type Values (Confirmed)

| load_type | Description | Confirmed |
|-----------|-------------|-----------|
| upsert | MERGE with WHEN MATCHED THEN UPDATE | ✓ |
| append | INSERT only | ✓ |
| overwrite_partition | Overwrite specific partition(s) | ✓ |
| overwrite | Full table overwrite | ✓ |
| scd2 | Slowly Changing Dimension Type 2 | ✓ |
| delete_insert | DELETE + INSERT pattern | ✓ |
| parquet_overwrite | Write to Parquet in ADLS | ✓ |

---

## Module Values (Confirmed from Schema)

Confirmed valid values for `module` field:
- Master Data
- Transport
- Topline
- Opex
- IMO & Fleet
- Selling & Delivery
- Plant Warehouse
- Distribution Warehouse
- Customer PnL
- Scenaio Modeling (note: typo "Scenaio" exists in source data)
- Workforce time data
- Trade
- CadDo-Deaverage
- Path To Market
- Manual File

---

## Table Type Values (Confirmed)

| table_type | Description | KPI Extraction? |
|------------|-------------|-----------------|
| Dimension | Dimension table | No |
| Fact | Fact table | Yes (if implementing KPI extraction) |
| Reference | Reference/lookup table | No |

---

## Output File Naming Patterns (Confirmed)

| SubProject | Output File |
|------------|-------------|
| PTS | `Copilot/LineageConfigJSON/Example_Lineage_Config.json` |
| CBV | `Copilot/LineageConfigJSON/Example2_Lineage_Config.json` |
| PostCadDo | `Copilot/LineageConfigJSON/<Project>_Lineage_Config.json` (if separate) |

---

## Known Limitations

### 1. Join Type Extraction
Currently `Join_Type` is set to "N/A" or not populated. Full join type extraction requires parsing notebook SQL beyond current scope. Marked as future enhancement.

### 2. Filter Logic Complexity
Complex filter conditions with subqueries, UDFs, or dynamic logic may not be fully captured in `Filters_Used[]` array. Skill focuses on system ID, reporting unit ID, and simple WHERE clause filters.

### 3. Manual Lineage Overrides
If user manually edits lineage JSON (e.g., adds custom sources), the skill should detect and preserve these entries. Current implementation: diff-based merge with user confirmation.

---

## Improvement Ideas for Future Runs

1. **Auto-detect SubProject from PL_Name prefix** — Eliminate need for user to specify
2. **Validate system IDs against xtn_system_master** — Warn if system ID doesn't exist in master table
3. **Extract transformation logic** — Parse notebook to generate business/technical transformation descriptions (like project-lineage-graph-pts Step 4)
4. **Dependency framework integration** — Add upstream/downstream pipeline dependencies from EDF job dependency tables
5. **iCEDQ rule integration** — Link to iCEDQ rule metadata for DQ validation rules

