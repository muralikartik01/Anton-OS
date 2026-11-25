---
name: gold-catalog
description: Generic Gold-layer Unity Catalog lookup skill for finding tables, schemas, and views in your organization's Gold (business-ready/consumption) layer via Databricks MCP. Requires the "Project → Catalog → Schema Quick Reference" section below to be filled in with your organization's actual deployed catalogs/schemas before use — ships as a template. Do NOT activate for generic 'gold standard', 'gold mining', or unrelated gold references.
---

# Gold Catalog — Business-Ready Data Layer

> **Setup required before first use**: This skill ships as a template. Fill in the **Project → Catalog → Schema Quick Reference** table (Section 0) with your organization's actual Gold catalogs/schemas, and adjust the audit-column names in Section 3 and the access-request process in Section 5 to match your organization's conventions. Everything else (query patterns, golden rules, merge strategies) works as-is against any Unity Catalog deployment.

## What This Skill Does

- **Gold Table Lookup**: Look up tables, schemas, and views in Gold layer Unity Catalogs using an MCP Databricks connection
- **Naming Convention Guidance**: Explain Gold catalog, schema, table, and view naming standards per environment and project
- **Governed-Access Guidance**: Explain secured/dynamic views and the access-request process (once configured for your org)
- **Project-Domain Mapping**: Map business domains/projects to their Gold schemas
- **Audit Columns Guidance**: Explain mandatory audit fields
- **Merge Strategy Reference**: Explain Upsert, SCD2, Append, Delete-Insert patterns
- **Silver-to-Gold Lineage**: Provide source-to-target mapping for Gold tables

## When To Use This Skill

Activate when a user asks about:
- Gold catalog, gold layer, gold tables, gold views
- Any project/domain name configured in Section 0 below
- Governed/secured views, row-level or column-level security on Gold data
- Which Gold table has X data? / Find gold table named Y
- What's in the Gold layer? / Show me Gold schemas
- Audit columns on Gold tables
- Merge strategy, upsert, SCD2, append, delete-insert

---

## Instructions

### ⚡ MANDATORY: Start Here — Intent-to-Query Shortcut

**Before running ANY query**, identify the user's intent and jump directly to the matching template below. Never run `SHOW CATALOGS`, `SHOW SCHEMAS`, or any exploratory query first — use the Quick Reference table in Section 0 to build the query directly.

| User Intent | Query Pattern |
|---|---|
| List tables in a project schema | `SELECT table_name FROM system.information_schema.tables WHERE table_catalog='<catalog>' AND table_schema='<schema>' ORDER BY table_name` |
| Find a specific Gold table by name | `SELECT table_catalog, table_schema, table_name FROM system.information_schema.tables WHERE table_catalog IN (<configured catalogs>) AND LOWER(table_name) LIKE '%<keyword>%' ORDER BY table_catalog, table_schema, table_name` |
| Get columns/details of a Gold table | `SELECT column_name, data_type, is_nullable, comment FROM system.information_schema.columns WHERE table_catalog='<catalog>' AND table_schema='<schema>' AND table_name='<table>'` |
| Find secured/shared views | `SELECT table_name FROM system.information_schema.tables WHERE table_catalog='<catalog>' AND table_schema='<secured_or_shared_schema>' ORDER BY table_name` |

> ## ⚠️ GOLDEN RULES — Read Before Every Action
>
> **1. Always Query Live Data — Never Answer From Memory**
> Before stating any table exists or does not exist, **always run a live MCP query** against `system.information_schema.tables` or `system.information_schema.columns`. Any table lists documented in this skill (or your project's own notes) are **illustrative examples only** — never cite them as facts. The MCP Databricks tool always executes a **fresh query against the SQL Warehouse** — it does not use cached or in-memory results.
>
> **2. Use Exact Catalog Names — Never Guess or Substitute a Placeholder**
> Always use the exact catalog names configured in the **Project → Catalog → Schema Quick Reference** table below. Do not assume all projects/domains are deployed in the same environment — some organizations deploy different domains to different environments (dev/qa/prod). Always check the table.
>
> **3. Scope Boundary — Unknown Projects**
> If the user asks about a project/domain not listed in the mapping table, respond: *"I don't have a catalog mapping for that project. Please check with your data platform team, or ask me to look it up via `SHOW CATALOGS`/`SHOW SCHEMAS` if you want an exploratory search."* Do **NOT** invent or guess a catalog name.

---

### ❌ FORBIDDEN First Steps (once Section 0 is configured)

**Never run these as a first step once the mapping table below is filled in — they are wasted round-trips:**
- `SHOW CATALOGS` — use the Project → Catalog mapping table instead
- `SHOW SCHEMAS IN <catalog>` — use the Project → Schema mapping table instead
- `SHOW TABLES IN <schema>` — use `system.information_schema.tables` instead
- Any query to count rows or check table types before retrieving actual data

*(If the mapping table is still empty/unconfigured for this workspace, these exploratory commands are the correct fallback — use them once, then propose adding the discovered catalogs/schemas to Section 0 for next time.)*

---

### 0. Project → Catalog → Schema Quick Reference

**⚠️ Fill this in for your organization before relying on the shortcuts above.** Leave rows empty/remove the example row if you haven't mapped your Gold deployment yet — the skill will fall back to `SHOW CATALOGS`/`SHOW SCHEMAS` discovery in that case.

| Project/Domain | Catalog | Gold Schema | Description |
|---|---|---|---|
| _{example — replace with your project}_ | `{your_catalog_name}` | `{your_gold_schema_name}` | _{what this domain covers}_ |

**Default Behavior**: Query all configured catalogs unless the user specifies a specific project or domain. If no catalogs are configured yet, ask the user which catalog(s) to search, or run `SHOW CATALOGS` once to discover candidates.

**Secured/shared views**: If your organization publishes governed cross-project views (row/column-level security), add their schema(s) to the table above too (e.g., a schema like `gold_share_vw` or `<project>_secured_vw`).

---

### Query Efficiency Guidelines

**Minimize queries** by using the most direct path to the data:

1. **For listing tables in a project**: Query the Gold schema directly (1 query) — use the Section 0 mapping
2. **For finding a specific table**: Search by table name with wildcards across configured catalogs (1 query)
3. **For table details**: Query `system.information_schema.columns` directly (1 query)
4. **Avoid exploratory queries**: Don't query table types/counts first; go straight to the target
5. **Filter in SQL**: Use `NOT LIKE '%test%'` to exclude test data in the same query

> **IMPORTANT — Never Write Programs to Parse Results**
> Do **NOT** write Python scripts, shell commands, or any code to process or parse query results returned by the MCP Databricks tool. All filtering, aggregation, and transformation must be done **inside the SQL query itself** using WHERE, GROUP BY, ORDER BY, LIKE, LIMIT, etc. Read the result values directly and present them to the user without any intermediate scripting.

> **IMPORTANT — Always Use LIMIT on Large Schemas**
> When querying schemas that may contain many tables, always apply a `LIMIT` (default: 50) and inform the user upfront: *"This schema has many tables — showing the top 50. Let me know if you'd like more or want to filter by a keyword."* Never silently return hundreds of rows without notifying the user of the truncation.

> **IMPORTANT — Warn Before Running Expensive Queries on Large Tables**
> When a user requests full table contents or queries without selective filters, first check approximate row count using:
> ```sql
> DESCRIBE DETAIL <catalog>.<schema>.<table_name>;
> ```
> Review the `numFiles`/statistics fields in the result. If the table appears to have **more than ~1,000,000 rows**, stop and warn the user before proceeding:
> *"⚠️ This table looks large. Running this query without filters could be expensive on the SQL Warehouse. Would you like to add filters (e.g., by a scope column, date, or partition column) before proceeding?"*
> Only proceed after explicit user confirmation. Always write highly efficient SQL: use partition filters, selective WHERE clauses, avoid `SELECT *`, and keep responses within token limits by using `LIMIT` where appropriate.

> **IMPORTANT — Ask Before Writing Any Script**
> If the result cannot be handled within SQL alone and a script seems necessary, **always ask the user first**: *"The result is too large to read directly — can I write a quick script to extract the data?"* Do **NOT** silently generate and run a script without explicit user confirmation.

---

### 0.A Table Lookup (Default Action)

When a user asks "does Gold have a table named X?" or "find table X in Gold layer":

1. **Use the MCP Databricks SQL tool** to search `system.information_schema.tables` across the catalogs configured in Section 0 (or all accessible catalogs if none are configured):

```sql
SELECT table_catalog, table_schema, table_name, table_type
FROM system.information_schema.tables
WHERE table_catalog IN (<configured catalogs>)
  AND (LOWER(table_name) LIKE '%<search_term>%'
       OR LOWER(table_schema) LIKE '%<search_term>%')
  AND table_name NOT LIKE '%test%'
  AND table_name NOT LIKE '%temp%'
ORDER BY table_catalog, table_schema, table_name;
```

2. **Interpret results** using Section 0's mapping to explain which project/domain the table belongs to and what kind of object it is (base Gold table, secured view, shared view).

3. **If not found**, explain:
   - The data may only exist in a Silver/staging layer
   - It may be a work-in-progress not yet deployed to Gold
   - Check if the table name uses a different naming convention or abbreviation

---

### 0.B List Gold Tables by Project

When a user asks "show me tables in project X":

**Use exactly ONE query** — look up the catalog and schema from Section 0 and run directly:

```sql
SELECT table_name, table_type
FROM system.information_schema.tables
WHERE table_catalog = '<catalog>'
  AND table_schema = '<schema>'
  AND table_name NOT LIKE '%test%'
  AND table_name NOT LIKE '%temp%'
  AND table_name NOT LIKE '%clone%'
ORDER BY table_name
LIMIT 100;
```

---

### 0.C Handling Permission Errors

**When attempting to query a Gold table and receiving permission errors** (e.g., `PERMISSION_DENIED`, `INSUFFICIENT_PRIVILEGES`, `User does not have USE SCHEMA`):

1. **Inform the user** that access to that specific Gold table has not been granted
2. **Explain** that the table exists but requires access onboarding — direct them to whatever access-request process your organization uses (see Section 5, once configured)

---

### 0.D Handling Zero Row Results

**When a query successfully executes but returns 0 rows**, this may indicate:

1. **Row-level security filtering** — the table exists and you can query it, but a row-level security policy filters out rows based on your scope/entitlement (e.g., market, source system, business unit)
2. **Empty table** — the table genuinely has no data yet (check if the pipeline has run)
3. **Incorrect filters** — the WHERE clause filters out all records

**How to diagnose**:

```sql
-- 1) Confirm the table exists
SELECT table_schema, table_name, table_type
FROM system.information_schema.tables
WHERE table_name = '<table_name>' AND table_catalog = '<catalog>';

-- 2) Check if it has any data at all (no filters)
SELECT COUNT(*) FROM <catalog>.<schema>.<table_name>;
```

If `COUNT(*)` returns 0, check whether the ETL pipeline has run successfully, whether the table is partitioned and needs a partition filter, and whether row-level security might apply.

---

### 0.E Getting Table Details

**When a user asks for "details" of a Gold table**, they typically want column name, description, data type, and identification of audit columns:

```sql
SELECT
    column_name,
    data_type,
    is_nullable,
    comment as column_description
FROM system.information_schema.columns
WHERE table_catalog = '<catalog>'
  AND table_schema = '<schema>'
  AND table_name = '<table_name>'
ORDER BY ordinal_position;
```

- `comment` contains the column description (may be NULL if not documented)
- `ordinal_position` ensures columns are returned in table definition order
- Cross-reference against Section 3 to flag which columns are mandatory audit columns

---

## 1. Gold Layer Overview

**Gold Layer** is the organization's business-ready, curated data layer, typically built on Databricks Unity Catalog. It provides:
- **Curated, business-ready data** aggregated and transformed from Silver/staging sources
- **Project-specific schemas** organized by business domain
- **Governed access** via secured/dynamic views (row-level and column-level security), where configured
- **Standardized audit fields** for traceability, compliance, and data lineage
- **Optimized for consumption** by analytics, reporting, and downstream applications

**Key Principle**: Gold tables are **consumption-ready** — all business logic, transformations, and aggregations have been applied. Consumers should NOT need to perform additional joins or complex transformations.

---

## 2. Gold Naming Conventions

These are **default conventions** — replace with your organization's actual naming standard if it differs.

### 2.1 Catalog Naming

A common pattern is:

```
<prefix>_<environment>_<domain>
```

| Component | Example values |
|---|---|
| `<prefix>` | An org/team identifier |
| `<environment>` | `dev`, `qa`, `preprod`, `prod` |
| `<domain>` | e.g. `supplychain`, `finance`, `gold` (for a shared/gold-share catalog) |

### 2.2 Schema Naming

```
<project_code>_gold                 -- base Gold schema
<project_code>_gold_secured_vw       -- secured view schema
<shared_schema_name>                 -- central shared/gold-share schema (e.g. gold_share_vw)
```

### 2.3 Table Naming

- Use **PascalCase**, descriptive business names (avoid abbreviations unless widely understood)
- Include **granularity indicators** in the name (e.g., `MonthlySummary`, `WeeklySummary`, `DailySummary`)
- Include **subject area** where relevant (e.g., `CustomerMaster`, `SalesPerformance`)

### 2.4 View Naming

```
<TableName>_vw            -- common/consumption view (auto-generated)
<TableName>_secured_vw    -- secured view (row/column-level security)
<project_code>_<table>    -- shared/cross-project view name
```

---

## 3. Mandatory Audit Columns (Defaults)

Replace these with your organization's existing audit-column convention if one is already defined.

| Column Name | Data Type | Null | Description |
|---|---|---|---|
| **MarketCode** | STRING | Not Null | Market/region/business-unit scope code |
| **SourceSystemId** | BIGINT/STRING | Not Null | Identifier of the originating source system |
| **ReportingUnitId** | STRING | Not Null | Reporting-unit identifier |
| **CreatedTimestamp** | TIMESTAMP | Not Null | Record creation timestamp in the Gold table |
| **CreatedBy** | STRING | Not Null | User/service account that created the record |
| **UpdatedTimestamp** | TIMESTAMP | Not Null | Last update timestamp |
| **UpdatedBy** | STRING | Not Null | User/service account that last updated the record |
| **RecordStatus** | STRING | Not Null | Record status (`ACTIVE`, `INACTIVE`, `DELETED`) |
| **SourceSystemKey** | STRING | Nullable | Source system primary key (for lineage) |

**Usage in Filters**: Row-level security policies, when present, often filter by scope columns like `SourceSystemId`, `MarketCode`, or `ReportingUnitId`. Always specify these columns when requesting access to Gold tables.

---

## 4. Merge Strategies

Gold tables use different merge strategies based on business requirements. These patterns are generic and apply to any Delta/Unity Catalog deployment.

### 4.1 Upsert (Default)

**When to use**: Master/dimension data, Slowly Changing Dimension Type 1 (overwrite changes).

```sql
MERGE INTO gold_table AS target
USING source_data AS source
ON target.merge_key = source.merge_key
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
```

### 4.2 SCD2 (Slowly Changing Dimension Type 2)

**When to use**: Historical tracking, audit trail of attribute changes, time-series analysis.

Key columns: `EffectiveStartDate` / `EffectiveEndDate`, `IsCurrent`, `VersionNumber`.

```sql
-- Close existing record
UPDATE gold_table SET EffectiveEndDate = current_date, IsCurrent = FALSE
WHERE merge_key = <key> AND IsCurrent = TRUE;

-- Insert new version
INSERT INTO gold_table VALUES (..., EffectiveStartDate = current_date, IsCurrent = TRUE);
```

### 4.3 Append

**When to use**: Transactional/fact tables, immutable event data, time-series data that never changes.

```sql
INSERT INTO gold_table
SELECT * FROM source_data
WHERE NOT EXISTS (SELECT 1 FROM gold_table WHERE merge_key = source_data.merge_key);
```

### 4.4 Delete-Insert (Partition Overwrite)

**When to use**: Aggregated summary tables partitioned by time period, full refresh of partition data.

```sql
DELETE FROM gold_table WHERE YearPeriodId = '<period>';
INSERT INTO gold_table SELECT * FROM source_data WHERE YearPeriodId = '<period>';
```

---

## 5. Governed Access Framework (Program-to-Program / Cross-Project Access)

> **Configure this section for your organization.** The pattern below (secured views + a central shared-views schema + an access-request UI or process) is a common design for governed Unity Catalog consumption — replace the placeholders with your actual tooling.

### 5.1 Overview

A governed-access framework is typically used for **program-to-program data sharing** (e.g., Project A consuming Project B's Gold data), distinct from individual user onboarding.

- **Access request tool**: `{your organization's access-request portal URL}`
- **Use case**: When one Gold program needs to consume data from another Gold program
- **Prerequisite**: Whatever network/VPN or authentication your organization requires

### 5.2 Key Roles (adjust to your org's governance model)

| Role | Responsibility |
|---|---|
| **Data Modeler** | Creates/updates access policies, defines row filters and restricted columns |
| **Data Steward** | Assigns policies to Policy Owners |
| **Policy Owner** | Approves/rejects program-to-program access requests |
| **Platform/Product Admin** | Program onboarding/offboarding & schema registration |

### 5.3 Individual User Access

For individual data engineers and analysts, direct them to your organization's standard access-request process (e.g., an internal portal or ticketing system) rather than the program-to-program governance tool above.

### 5.4 Secured View Schema Patterns

| View Type | Schema Pattern |
|---|---|
| **Project Secured View** | `<project>_gold_secured_vw` |
| **Shared/Gold-Share View** | `<shared_schema_name>` (e.g. `gold_share_vw`) |

---

## 6. Common Gold Tables by Project

> This section is intentionally left as a **placeholder** — populate it with your organization's actual deployed Gold tables per project/domain once discovered, or skip it and always rely on live MCP queries (Section 0 Golden Rule #1). Do **not** hardcode example tables here that don't exist in your workspace; that misleads future lookups.

| Project/Domain | Catalog | Schema | Notable Tables (fill in as discovered) |
|---|---|---|---|
| _{fill in}_ | | | |

---

## 7. Silver-to-Gold Lineage

Document your organization's actual Silver→Gold transformation patterns here once known, e.g.:

| Silver/Staging Source | Gold Table | Transformation Type |
|---|---|---|
| _{fill in}_ | _{fill in}_ | _{e.g. join + business rules + audit columns}_ |

---

## 8. FAQ — Gold Layer

**Q: What's the difference between Gold and Silver/staging?**
Silver/staging is cleansed, standardized data from source systems — the source of truth for raw enterprise data, primarily for data engineering teams. Gold is business-ready, curated data with all transformations, aggregations, and business logic applied, organized by project/use case, optimized for consumption.

**Q: How do I request access to a Gold table?**
Individual users → your organization's standard access-request process. Program-to-program sharing → the governed-access framework in Section 5 (once configured).

**Q: Which environment should I use for development?**
Use the exact catalog names from the Section 0 mapping table — different domains may be deployed to different environments; never assume.

**Q: What are the mandatory audit columns in Gold tables?**
See Section 3.

**Q: How do I find out which Silver tables a Gold table uses?**
Check your organization's lineage documentation (Section 7 once populated), or the Gold table's `comment`/documentation field for listed source tables.

**Q: What merge strategy does my table use?**
See Section 4 for all patterns (Upsert, SCD2, Append, Delete-Insert).

**Q: Can I write directly to Gold tables?**
Typically **no** — Gold tables are read-only for consumers. Only ETL pipelines should write to Gold. To update Gold data: update the source in Silver/staging, then trigger/rerun the Gold ETL pipeline.

**Q: How do I know if a Gold table has row-level security?**
Check with your platform team or governed-access tooling (Section 5) — if the table has policies assigned, it has row-level security.

---

## 9. Contact & Support

> Replace these placeholders with your organization's actual contacts/distribution lists.

| Issue Type | Contact |
|---|---|
| **Individual User Access** | `{your organization's access-request portal}` |
| **Program-to-Program Access** | `{Data Modeler / Policy Owner contact}` |
| **Gold Schema Creation** | `{platform team contact}` |
| **Gold Pipeline Issues** | `{product DevOps contact}` |
| **Gold Data Quality Issues** | `{data quality lead contact}` |
| **General Gold Questions** | `{product tech lead contact}` |

---

## 10. Summary

**Gold Layer Quick Facts:**
- **Purpose**: Business-ready, curated data layer for consumption
- **Organization**: Project-specific schemas
- **Catalog to Use**: Always look up the exact catalog from the Section 0 mapping table — never guess
- **Access Model**: Individual users via standard onboarding; program-to-program via governed-access framework (Section 5)
- **Mandatory Audit Columns**: Section 3
- **Merge Strategies**: Section 4
- **Naming**: PascalCase table names, `<project>_gold` schemas, shared schema for cross-project consumption

**Key Principles**:
- Gold is **consumption-ready** — no further transformations needed by consumers
- Always **verify table existence via live MCP query** before stating facts
- Always **warn users before expensive queries** (large tables)
