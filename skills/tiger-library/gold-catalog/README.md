# Gold Catalog (Business-Ready Data Layer)

## Overview

This skill helps data engineers discover, explore, and understand Gold-layer tables in a Unity Catalog deployment. It provides guidance on Gold naming conventions, project schemas, audit columns, merge strategies, and governed access to secured views.

**This skill ships as a template.** Before relying on its "no exploratory query" shortcuts, fill in Section 0 of `SKILL.md` (the Project → Catalog → Schema mapping) with your organization's actual deployed Gold catalogs/schemas.

## What This Skill Does

- **Table Discovery**: Query Gold catalogs using MCP Databricks SQL to find tables across projects
- **Schema Mapping**: Map business domains to Gold schemas (once Section 0 is configured)
- **Naming Conventions**: Explain environment-specific catalog names, schema patterns, and PascalCase table naming
- **Audit Column Guidance**: Document mandatory fields (`MarketCode`, `SourceSystemId`, `ReportingUnitId`, etc. — rename to your org's convention)
- **Merge Strategies**: Explain Upsert, SCD2, Append, and Delete-Insert patterns
- **Governed Access**: Guide users through secured-view access and policy-based consumption (once your org's process is documented in Section 5)
- **Silver-to-Gold Lineage**: Show source mappings from staging/Silver to Gold layer (once documented in Section 7)

## When to Use

Activate this skill when users ask about:
- Gold catalog, gold layer, gold tables, gold views
- Any project/domain configured in Section 0
- Secured views, row/column-level security on Gold data
- Audit columns, merge strategies, business-ready data
- Finding specific Gold tables or listing project schemas
- Access requests to Gold data

## Key Features

### 1. Project-Specific Schemas

Configure this table in `SKILL.md` Section 0 for your deployment:

| Project | Catalog | Schema | Description |
|---|---|---|---|
| _{fill in}_ | _{fill in}_ | _{fill in}_ | _{fill in}_ |

### 2. Mandatory Audit Columns (defaults — rename to your org's convention)

- `MarketCode` (STRING, Not Null)
- `SourceSystemId` (BIGINT/STRING, Not Null)
- `ReportingUnitId` (STRING, Not Null)
- `CreatedTimestamp` (TIMESTAMP, Not Null)
- `CreatedBy` (STRING, Not Null)
- `UpdatedTimestamp` (TIMESTAMP, Not Null)
- `UpdatedBy` (STRING, Not Null)
- `RecordStatus` (STRING, Not Null)

### 3. Merge Strategies

- **Upsert**: Master/dimension data
- **SCD2**: Historical tracking with effective dates
- **Append**: Transactional/fact tables
- **Delete-Insert**: Aggregated summaries (partition overwrite)

### 4. Governed Access

Secure, policy-based access to Gold tables (pattern — configure for your org):
- Row-level security filtering
- Column-level masking
- Access via a secured-view or shared-view schema
- Request access via your organization's access-request process

## Example Queries

### Find a Gold table by name
```sql
SELECT table_catalog, table_schema, table_name
FROM system.information_schema.tables
WHERE table_catalog IN ('<catalog1>', '<catalog2>')
  AND LOWER(table_name) LIKE '%<keyword>%'
ORDER BY table_catalog, table_schema, table_name;
```

### List all tables in a project's Gold schema
```sql
SELECT table_name, table_type
FROM system.information_schema.tables
WHERE table_catalog = '<catalog>'
  AND table_schema = '<schema>'
ORDER BY table_name;
```

### Get table details (columns, types)
```sql
SELECT column_name, data_type, is_nullable, comment
FROM system.information_schema.columns
WHERE table_catalog = '<catalog>'
  AND table_schema = '<schema>'
  AND table_name = '<table>'
ORDER BY ordinal_position;
```

## Key Differences: Gold vs. Silver/Staging

| Aspect | Silver/Staging | Gold |
|---|---|---|
| **Purpose** | Source-of-truth, cleansed data | Business-ready, curated data |
| **Organization** | By domain (customer, material, finance) | By project/use case |
| **Transformations** | Minimal (cleansing, standardization) | Full business logic, aggregations |
| **Consumption** | Primarily for Gold layer builds | Direct consumption by business users |
| **Access Model** | Dynamic views with row-level security | Governed access framework (policy-based) |

## Quick Start

1. **Find a Gold table**: Ask "Does Gold have a table named X?"
2. **List project tables**: Ask "Show me all tables in project Y"
3. **Get table details**: Ask "What columns are in schema.table Z?"
4. **Check lineage**: Ask "Which Silver tables feed table Z in Gold?"
5. **Request access**: Follow your organization's access-request process (Section 5 of SKILL.md)
