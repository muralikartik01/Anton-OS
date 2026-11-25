---
name: lineage-extraction
description: 'Generate Gold-table lineage JSON from Databricks audit tables via MCP server. Extracts Gold table lineage with sources, schedules, DQ config, hierarchies (Market→Sector→Module→TableType). Output to LineageConfigJSON/ with incremental merge. Use when: build lineage, update lineage for new tables/pipelines, validate lineage completeness, trace dependencies, onboard Gold tables. Trigger: lineage extraction, generate lineage, update lineage, Gold table sources, pipeline lineage.'
---

# Gold Table Lineage Extraction

> **Setup required before first use**: This skill was built against one specific real-world audit-metadata schema (an `audit_parameters` table with numbered source slots 1–12, plus an `edfdataassetdetails`-style reference table for system-ID validation — see `references/reference_tables.yaml`). It ships as a **worked example**, not a drop-in tool: before using it, either (a) replicate an equivalent audit-metadata table/schema in your own workspace, or (b) adapt `references/queries.md` and `references/reference_tables.yaml` to point at your organization's actual pipeline-metadata tables and column names. The business-unit/market codes (`BU1`–`BU6`) and catalog placeholders (`{audit_catalog}`, `{silver_catalog}`, `{gold_catalog}`) throughout this skill are examples — replace them with your organization's real values.

Generate hierarchical, market-grouped lineage JSON for Gold tables by querying Databricks Unity Catalog audit tables via MCP server.

## When To Use

- Generate lineage JSON for new Gold tables or pipelines
- Update existing lineage for modified pipelines
- Validate lineage completeness across markets
- Trace source-to-target data flow
- Audit source coverage and system IDs
- Onboard new Gold tables to lineage tracking

## Output Location

All lineage JSON files are written to: `Copilot/LineageConfigJSON/`

File naming pattern: `<Project>_Lineage_Config.json`
- Example: `Example_Lineage_Config.json`, `Example2_Lineage_Config.json`

## Output Schema

Hierarchical JSON structure grouped by market, aligned with `references/lineage_schema.json`:

```json
{
  "lineage_metadata": {
    "version": "2.1",
    "created_date": "YYYY-MM-DD",
    "description": "Gold to Silver/Bronze lineage tracking for Program <SUBPROJECT>",
    "project": "<Project>",
    "project_full_name": "<Your Program Full Name> - <SubProject Full Name>",
    "source_type_legend": {},
    "generated_from": "lineage-extraction skill",
    "registry_generated_at": "ISO timestamp"
  },
  "markets": [
    {
      "market_code": "US",
      "market_name": "US - United States",
      "business_unit_name": "BU1",
      "business_unit_key": "BU1",
      "gold_tables": [
        {
          "gold_table_name": "product",
          "gold_table_full_name": "{gold_catalog}.{gold_schema}.product",
          "pipeline_name": "PL_Example_BU1_US_Product",
          "sector_name": "BU1",
          "market_name": "US",
          "load_type": "upsert",
          "workflow_name": "Example_Workflow_Global_Small",
          "notebook_path": "/Workspace/{your_workspace_path}/...",
          "schedule": {
            "frequency": "W",
            "day": "Monday",
            "hour": "12",
            "minute": "30"
          },
          "module": "Master Data",
          "table_type": "Dimension",
          "dq_config": {
            "dq_flag": "Y",
            "dq_dataset_name": "...",
            "dq_dataset_layer": "GOLD"
          },
          "SourceSystemId": "1961",
          "ReportingUnitId": "107242",
          "Sources": [
            {
              "Source_Table_Type": "Silver",
              "Table_Name": "{silver_catalog}.fdn_material_view.xcfmaterialcore",
              "Table_ShortName": "xcfmaterialcore",
              "Catalog": "{silver_catalog}",
              "Schema": "fdn_material_view",
              "SourceSystemId": "1961",
              "ReportingUnitId": "107242",
              "Filters_Used": ["SourceSystemId = 1961", "ReportingUnitId = 107242"],
              "Join_Type": "LEFT JOIN"
            }
          ]
        }
      ]
    }
  ],
  "system_id_reference": {
    "description": "Reference for System IDs used across markets",
    "system_ids": [...]
  }
}
```

> **Identifier Rule**: `SourceSystemId` and `ReportingUnitId` are REQUIRED on all target Gold table entries. For per-source fallback logic, see Step 3 of the Extraction Procedure below.

## Extraction Procedure

### Prerequisites

> ⛔ **MANDATORY BEFORE ANY MCP QUERY**: Read `references/queries.md` in full FIRST. Do NOT guess table paths or write queries from memory. The correct catalog, schema, and full column list are defined there. Any query run before reading `references/queries.md` is invalid.

1. **Read `references/queries.md`**: Load the full file before running any Databricks query — this defines the exact SQL for all 4 queries including the correct catalog (`{audit_catalog}.{audit_schema}`) and all 12 source slots
2. **Read Input Scope**: Load `references/input_scope.yaml` to determine which Gold tables/pipelines to process
3. **Load Reference Tables**: Read `references/reference_tables.yaml` for audit table locations
4. **Read Existing Lineage**: Load existing JSON from `Copilot/LineageConfigJSON/` if present
5. **Initialize MCP Connection**: Ensure Databricks MCP server is available for querying

### Step 1 — Query Audit Parameters

For each entry in `input_scope.yaml`, query `audit_parameters` table via MCP:

**Full query**: See [Query 1 — Audit Parameters](references/queries.md#query-1--audit-parameters) in `references/queries.md`.

> ⛔ **COPY THE QUERY VERBATIM** — do NOT rewrite or shorten it. Query 1 includes source slots 1 (primary, no suffix) through 12. All 12 slots MUST be present in the single MCP call. Never split into multiple calls or truncate at slot 8.

Extract:
- Target table 3-part name: `{target_catalog}.{target_schema}.{target_table}`
- All source tables: primary (no suffix) + suffixes 2 through 12 — check all 12 slots; stop when catalog/table fields are empty
- Per-source system IDs: `source_SourceSystemId` / `source_ReportingUnitId` (primary) and `source_SourceSystemId2..12` / `source_ReportingUnitId2..12` — map each to its corresponding source entry
- Load type (upsert, append, overwrite_partition, scd2, delete_insert)
- DQ configuration (dq_dataset_name, dq_flag)
- Hierarchy metadata (SectorName, MarketName, module, table_type)
- Notebook path and optional query parameter

---

### Step 1a — Detect and Parse Query-Based Pipeline

After executing Query 1, determine whether the pipeline is **query-based** or **slot-based**:

| Pipeline Type | Condition | Action |
|---|---|---|
| **Slot-based** | At least one `source_catalog_name` + `source_table_name` pair is non-NULL | Proceed to Step 2 using populated slot values |
| **Query-based** | ALL `source_catalog_name` and `source_table_name` slots (1–12) are NULL/empty | Parse the `query` field SQL to extract sources — see below |

> ⚠️ For query-based pipelines, the `query` field in `ParameterValue` is the **single source of truth** for all source tables. Source slots 1–12 remain empty in `audit_parameters` and must be **populated via upsert** after extraction (see Step 3a-2).

#### Parsing the `query` Field

Scan the embedded SQL string for:

1. **Source table references** — find all 3-part `catalog.schema.table` patterns in `FROM`, `JOIN`, CTE body references, and subquery `FROM` clauses. Use a pattern such as:
   ```
   \buc_[a-z0-9_]+\.[a-z0-9_]+\.[a-z0-9_]+\b
   ```
   Also capture ADLS paths (`abfss://...`) as Parquet sources.

2. **Per-source filters** — for each source found, scan the SQL context around that table reference (its CTE body, WHERE clause, or JOIN ON condition) for **two categories**:

   **a) System ID filters** (used to populate `SourceSystemId` / `ReportingUnitId`):
   - `SourceSystemId = <value>` or `SourceSystemId IN (<values>)`
   - `ReportingUnitId = <value>` or `ReportingUnitId IN (<values>)`
   - Legacy column aliases: `SystemId = '<value>'`, `SystemCode = '<value>'` — **production source of truth**: if the production SQL uses `SystemId=<value>`, use that value directly as `SourceSystemId` for that source. Record it in both `SourceSystemId` and `Filters_Used`. Do NOT override with EDF values (see Step 3a exception).

   **b) All other significant WHERE predicates** — capture every non-trivial filter on that source table regardless of column name. This includes (but is not limited to): business key filters (`TargetSystemID = 'X'`, `SourceSystemID = 'Y'`), configuration filters (`ReferenceConfigurationId = 'Z'`), status filters (`RecordStatus = 'ACTIVE'`, `ActiveFlag = 'Y'`), type/code filters (`MaterialUnitofMeasureCode IN ('CRU', 'CS')`), and any other equality or IN-list predicates applied to that specific CTE or subquery. Do **not** capture JOIN ON conditions or predicates that belong to a different source table's CTE.

   Add all captured values — both categories — as individual strings in `Filters_Used` on the source entry.

3. **Assign source slot numbers** — number discovered sources sequentially (slot 1, 2, 3…) by order of first appearance in the SQL. Deduplicate: if the same table appears in multiple CTEs or JOIN branches, count it once using the first occurrence.

4. **Classify each source** using the same rules as Step 2 (Bronze/Silver/Gold/Parquet).

> ⚠️ **Query field truncation — active retrieval required**: MCP tool output truncates long string values at display time. Do NOT rely on the initial Query 1 response alone for the `query` field. After Query 1, **always** run the following two-step check:
>
> **Step A — Measure full length**:
> ```sql
> SELECT LENGTH(get_json_object(ParameterValue, '$.query')) AS query_len
> FROM {audit_catalog}.{audit_schema}.audit_parameters
> WHERE PL_Name = '<pipeline_name>'
> ```
>
> **Step B — Retrieve in chunks if > 1800 chars**: If `query_len` exceeds 1800, fetch the remaining text in sequential 4000-character chunks until the full string is recovered:
> ```sql
> -- Chunk 2 (chars 1801–5800), adjust offsets for each subsequent chunk
> SELECT SUBSTRING(get_json_object(ParameterValue, '$.query'), 1801, 4000) AS query_chunk
> FROM {audit_catalog}.{audit_schema}.audit_parameters
> WHERE PL_Name = '<pipeline_name>'
> ```
> Concatenate all chunks before parsing. Only after the full SQL string is assembled should source table extraction and filter parsing (points 1 and 2 above) be performed. If `query_len` ≤ 1800, the initial Query 1 value is complete — no additional fetch needed.

---

### Step 2 — Determine Source Table Type

For each source table, classify as Bronze/Silver/Gold/Parquet using these rules:

| Condition | Source_Table_Type |
|-----------|-------------------|
| Catalog = `{silver_catalog}` AND Schema contains `bronze` | **Bronze** |
| Catalog = `{silver_catalog}` AND Schema does NOT contain `bronze` or `gold` | **Silver** |
| Catalog ≠ `{silver_catalog}` AND Schema contains `gold` | **Gold** |
| Catalog contains `mosaic` AND Schema contains `gold` | **Gold** |
| Source is ADLS path (abfss://) | **Parquet** |
| Manual table or external reference | **Reference** |

**Environment Placeholder**: Always use `{env}_` in output (do not parameterize by environment).

### Step 3 — Extract System IDs and Filters

For each source table, identify:

**Priority order for per-source SourceSystemId / ReportingUnitId**:
1. **Audit param fields** (`source_SourceSystemId<N>` / `source_ReportingUnitId<N>`) — use directly if non-empty (slot-based pipelines only)
2. **From `query` field SQL** (Step 1a) — for query-based pipelines, the SourceSystemId / ReportingUnitId filters parsed from the embedded SQL are the primary source of per-table IDs
3. **From dedicated notebook** (if `query` is NULL) — read notebook source, parse `.filter()` / `.where()` calls
4. **Fallback**: inherit target table's system/reporting unit IDs if no per-source value found
5. **"N/A"** for Parquet / Bronze / Reference sources. **Gold sources**: check `query` key in `ParameterValue` (audit parameters) — if present, parse for ID filters; if `query` key is empty, note the notebook path from the `nb_path` key; default to "N/A" only if neither yields IDs (see Step 3b)

> **Query-based pipelines**: ALL sources come from Step 1a SQL parsing. Source slots 1–12 in `audit_parameters` are empty and will be populated by upsert code generated in Step 3a-2.

Always populate `SourceSystemId` and `ReportingUnitId` on each `Sources[]` entry, even if "N/A".

> ⚠️ **Silver source IDs are always validated against `edfdataassetdetails` in Step 3a** — even when values appear populated, they may be incorrect. Fix code is generated whenever the EDF values differ from the current values, or when current values are empty.
> ⚠️ **Gold source ID filters are always checked via `query`/`nb_path` in Step 3b** — if filters are present in the query or notebook, those values must be captured in lineage.

Store in `Filters_Used` array as individual filter strings:
```json
"Filters_Used": [
  "SourceSystemId = 1961",
  "ReportingUnitId = 107242",
  "StatusCode = 'ACTIVE'"
]
```

### Step 3a — Validate Silver Source System IDs via EDF Data Asset Details

After completing Step 3, run this validation step for **every** source entry where `Source_Table_Type` is **Silver** — regardless of whether IDs are already populated. Existing values may be incorrect.

**Scope**: All Silver sources without exception.

**Skip** this step for: Bronze, Gold, Parquet, and Reference source types.

#### 3a-1 — Query edfdataassetdetails and Compare

For each pipeline, collect all `Table_ShortName` values from Silver sources and run **one batched Query 4** from `references/queries.md`:
- Lowercase all shortnames and pass as `LOWER(SilverTableName) IN ('<name1>', '<name2>', ...)`
- After the query returns, match results back to source entries by `LOWER(SilverTableName) = LOWER(Table_ShortName)`

Column mapping from the result:
- `DataFoundationSystemID` → compare against current `SourceSystemId`
- `DataFoundationReportingUnitID` → compare against current `ReportingUnitId`

**Comparison outcomes**:

| EDF result | Current value | Action |
|---|---|---|
| Returns values | Matches current | ✓ Confirmed correct — no fix needed |
| Returns values | Differs from current OR current is empty/N/A | ⚠️ Mismatch — update in-memory value to EDF value; flag for fix code in Step 3a-2 |
| No rows returned | Any | ⚠️ Log `[WARN] No EDF asset record found for Silver table '<Table_ShortName>' in pipeline '<PL_Name>'`; keep current value; flag for user review in summary |
| Multiple rows with distinct ID pairs | Any | Use first non-null result; log `[WARN] Multiple EDF asset records found for '<Table_ShortName>' — using first result; manual review recommended` |

> ⚠️ **Exception — Legacy `SystemId` in SQL**: If the pipeline's SQL query already filters a Silver source by `SystemId=<value>` (not `SourceSystemId`), that value is the **production source of truth** for `SourceSystemId`. Keep that value and **skip EDF override for the system ID**. EDF may still be used to populate a missing `ReportingUnitId` if absent.

When updating in-memory values due to mismatch, also update `Filters_Used` to reflect the corrected IDs.

#### 3a-2 — Generate audit_parameters Fix Code

After processing all Silver sources across all pipelines in scope, collect every pipeline+source slot where the EDF lookup returned values that **differ from the current audit_parameters values** (including cases where the current value was empty or N/A). Group pipelines that share the **same slot number and the same corrected values** into a single code block.

For each group, generate a Python snippet using the `upsert_audit_parameters` function:

```python
# Fix empty system IDs — source slot <N> (primary = no suffix, otherwise slot 2-12)
pl_names = [
    '<pipeline_name_1>',
    '<pipeline_name_2>'   # include all pipelines sharing the same slot + values
]
parameters = {
    "source_SourceSystemId<N>": "<DataFoundationSystemID>",
    "source_ReportingUnitId<N>": "<DataFoundationReportingUnitID>"
}

for pl_name in pl_names:
    try:
        upsert_audit_parameters(pl_name, parameters)
    except:
        print(f"Error: {pl_name}")
```

**Key rules when generating these blocks**:
- For the **primary** source slot (no suffix), use keys `"source_SourceSystemId"` and `"source_ReportingUnitId"` (no number)
- For slots 2–12, use keys `"source_SourceSystemId<N>"` and `"source_ReportingUnitId<N>"` (e.g. `source_SourceSystemId3`)
- Substitute `<N>`, `<pipeline_name_*>`, `<DataFoundationSystemID>`, and `<DataFoundationReportingUnitID>` with actual values
- Group pipelines with identical slot + values in the same block to minimise noise
- `upsert_audit_parameters` is an **upsert** (insert-or-update) — if a key does not yet exist in the pipeline's `ParameterValue` JSON, it is inserted as a new entry; if it already exists, it is updated in place

**Query-based pipelines — extended upsert code** (when all source slots were NULL and sources were extracted from the `query` field):

> ⚠️ **Query-based pipeline scope**: Generate one code block per **every** source slot discovered (Silver, Bronze, Gold, Parquet) — not only enriched Silver sources. Because audit_parameters contains no slot data at all, every slot must be populated. Bronze, Gold, and Parquet slots use `""` for system ID fields.

For query-based pipelines, the fix code must insert ALL five fields per source slot, not just the system ID keys:

```python
# Insert source table slots extracted from embedded SQL query — slot <N>
# Run AFTER confirming EDF system IDs via Step 3a-1
pl_names = [
    '<pipeline_name>'
]
parameters_slot_<N> = {
    "source_catalog_name<N>": "<catalog>",
    "source_schema_name<N>": "<schema>",
    "source_table_name<N>": "<table_name>",
    "source_SourceSystemId<N>": "<DataFoundationSystemID>",    # from EDF or SQL filter; "" if N/A
    "source_ReportingUnitId<N>": "<DataFoundationReportingUnitID>"  # from EDF or SQL filter; "" if N/A
}

for pl_name in pl_names:
    try:
        upsert_audit_parameters(pl_name, parameters_slot_<N>)
    except:
        print(f"Error: {pl_name}")
```

- Primary slot (no suffix): omit the `<N>` suffix on all five keys (e.g. `source_catalog_name`, `source_table_name`, `source_SourceSystemId`)
- Slots 2–12: append the number (e.g. `source_catalog_name3`, `source_table_name3`, `source_SourceSystemId3`)
- For Bronze, Gold, Parquet, and Reference sources: set `source_SourceSystemId<N>` and `source_ReportingUnitId<N>` to `""` (empty string, not "N/A"), since these slot keys are not applicable
- Generate one code block per slot — do NOT batch all slots into one `parameters` dict, as each slot is independently addressable

**Print all generated code blocks to the user in chat**, grouped by slot, before proceeding to Step 4. Do NOT execute them — the user is responsible for running them.

---

### Step 3b — Check Gold Source System ID Filters

After completing Step 3a, for every source entry where `Source_Table_Type` is **Gold**:

**Skip** this step for: Bronze, Silver, Parquet, and Reference source types.

1. **Check `query` key**: From audit_parameters `ParameverValue` where `key = 'query'` for the same pipeline:
   - If **query is present**: parse the SQL WHERE clause for `SourceSystemId = <value>` or `IN (<values>)` and `ReportingUnitId = <value>` or `IN (<values>)`. If found, set those values on the source entry and populate `Filters_Used` accordingly.
   - If **query key is empty or NULL**: read the `nb_path` key from audit_parameters to get the notebook path. Log `[INFO] Gold source '<Table_Name>' in '<PL_Name>' uses notebook '<nb_path>' — system ID filters should be verified in notebook source`.
2. If neither the query nor notebook check yields ID values, set `SourceSystemId = "N/A"` and `ReportingUnitId = "N/A"`, and log `[WARN] Gold source '<Table_Name>' in '<PL_Name>': no system ID filters found in query or notebook`.
3. **No fix code is generated** for Gold sources — this is a lineage accuracy check only.

---

### Step 4 — Query Job Schedule

Query `job_schedule` table to get workflow schedule:

**Full query**: See [Query 2 — Job Schedule](references/queries.md#query-2--job-schedule) in `references/queries.md`.

Map to schedule object:
```json
"schedule": {
  "frequency": "W",          // D=Daily, W=Weekly, FP=FinancialPeriod, FILEWATCH, M=Monthly
  "day": "Monday",           // Day name or date
  "hour": "12",
  "minute": "30"
}
```

### Step 5 — Build Market Hierarchy

Group Gold tables by `market_code` from `MarketName` field in audit_parameters.

**CRITICAL: Pipeline is the unique identifier** — if a Gold table is loaded by multiple pipelines, create **separate entries** for each pipeline. Each pipeline gets its own entry in the JSON, even if targeting the same Gold table.

Market metadata:
- `market_code`: Country code from `MarketName` field (US, CA, MX, BR, CN, AU, etc.)
- `market_name`: Full country name (US - United States, MX - Mexico, BR - Brazil, etc.)
- `business_unit_name`: Sector name — MUST be one of 6 valid sectors: **BU1, BU2, BU3, BU4, BU5, BU6**
- `business_unit_key`: Same as business_unit_name

**Sector Mapping Rules** (when `SectorName` from audit doesn't match the 6 valid values):
- BU_ALT1 (Example Manufacturing Unit) → **BU3**
- Global / NA / your organization → Infer from `MarketName` country code:
  - US, CA → **BU1** (Business Unit 1 (example))
  - MX, BR, AR, CL → **BU3** (Latin America)
  - CN, AU, JP, IN → **BU5** (Asia Pacific)
  - UK, DE, FR, PL → **BU6** (Europe)
  - ZA, EG, KE → **BU4** (Africa, Middle East, South Asia)
- If ambiguous, use **Global** market under **BU1** sector as default

### Step 6 — Query System ID Reference

Query Unity Catalog system master for system names:

**Full query**: See [Query 3 — System ID Master](references/queries.md#query-3--system-id-master) in `references/queries.md`.

Build `system_id_reference.system_ids[]` section with unique system/reporting unit combinations.

### Step 7 — Merge with Existing Lineage

**CRITICAL**: Never overwrite existing lineage JSON — always merge incrementally.

1. **Load existing JSON** from `Copilot/LineageConfigJSON/<Project>_Lineage_Config.json`
2. **Compare new entries** with existing:
   - Primary key: `(market_code, gold_table_name, pipeline_name)`
   - If entry exists: show diff and ask user for confirmation to update
   - If new entry: add to appropriate market's `gold_tables[]` array
3. **Preserve all existing entries** not in current scope
4. **Update metadata**: `registry_generated_at` timestamp, increment version if schema changes
5. **Write merged JSON** back to `Copilot/LineageConfigJSON/`

**Diff Format** (when asking user):
```
Table: {gold_schema}.product (Pipeline: PL_Example_BU1_US_Product, Market: US)

CHANGES DETECTED:
  - load_type: "upsert" → "overwrite_partition" 
  + Sources: Added 2 new source tables
    + {silver_catalog}.fdn_material_view.materialplant
    + {gold_catalog}.{gold_schema}.location
  ~ schedule.day: "Monday" → "Tuesday"

Accept changes? (Y/N)
```

### Step 8 — Validate Output

Run `scripts/eval_lineage.py` to validate:
1. Schema compliance (all required fields present)
2. Source table type validity (Bronze/Silver/Gold/Parquet only)
3. Market grouping correctness
4. System ID consistency
5. No orphaned entries (every Gold table has at least one source)

Log validation results to `lineage_eval_results.tsv`.

## Self-Improving Eval Loop

### Phase 1 — Review Before Generating

Read these files before extraction:
- `references/lineage_schema.json` — Output schema contract
- `references/reference_tables.yaml` — Audit table locations
- `references/config_patterns.md` — Known extraction patterns
- `references/learnings.md` — Historical fixes and edge cases
- `lineage_eval_results.tsv` — Past eval outcomes

### Phase 2 — Generate and Evaluate

After each extraction run:
1. Execute `scripts/eval_lineage.py` on new/updated JSON
2. Inspect failures (schema violations, missing IDs, orphaned tables)
3. Fix extraction logic for narrowest scope explaining failure
4. Rerun until validation passes or manual review needed

### Phase 3 — Improve Next Run

- Append confirmed patterns to `references/learnings.md`
- Record eval outcome in `lineage_eval_results.tsv`
- Update `references/config_patterns.md` with new notebook/query patterns discovered

## Key Rules

1. **Pipeline is the unique key** — one JSON entry per pipeline, not per Gold table. If a Gold table is loaded by multiple pipelines, create separate entries for each pipeline.
2. **Never guess missing data** — if system ID / reporting unit ID cannot be extracted, use "N/A" and log warning
3. **Always merge incrementally** — never replace existing lineage file wholesale
4. **Market grouping is mandatory** — every Gold table must belong to a market
5. **Sector must be one of 6 valid values** — BU1, BU2, BU3, BU4, BU5, BU6. Map non-standard values (BU_ALT1, Global, NA) using sector mapping rules in Step 5.
6. **Market is country code** — MarketName field contains country codes (US, CA, MX, BR, CN, AU), not sector names
7. **Source table type must be deterministic** — follow Step 2 rules exactly
8. **Preserve manual overrides** — if user manually edited lineage JSON, detect and skip those entries
9. **Validate before write** — run eval script and block write on critical failures

## Input Scope File Format

`references/input_scope.yaml`:

```yaml
# Lineage Extraction Input Scope
# Specify which Gold tables/pipelines/notebooks to process
# Leave list empty to skip lineage extraction

entries:
  - object_type: table
    object_name: {gold_catalog}.{gold_schema}.product
    
  - object_type: pipeline
    object_name: PL_Example_BU1_US_Product
    
  - object_type: notebook
    object_name: /Workspace/{your_workspace_path}/PTS/BU1/US/NB_Example_BU1_US_Product
    
  # Can also specify wildcards for batch processing
  - object_type: table
    object_name: {gold_catalog}.{gold_schema}.*  # All tables in schema
```

**Processing Logic**:
- `object_type: table` → Query audit_parameters WHERE target table matches
- `object_type: pipeline` → Query audit_parameters WHERE PL_Name matches
- `object_type: notebook` → Query audit_parameters WHERE nb_path matches
- Wildcards (`*`) supported for batch extraction

## References

- `references/queries.md` — All SQL queries used for lineage extraction (audit parameters, job schedule, system ID master)
- `references/lineage_schema.json` — Complete JSON schema with examples
- `references/reference_tables.yaml` — Databricks audit table locations
- `references/config_patterns.md` — Common extraction patterns
- `references/learnings.md` — Historical fixes and edge cases
- `references/input_scope.yaml` — User input for extraction scope
- `scripts/eval_lineage.py` — Validation harness