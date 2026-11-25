# STTM Field Mappings

## Source Columns — Populate from DAT

| STTM Field | Source | Value |
|-----------|--------|-------|
| Source Name | DAT | `Silver Layer` or the source layer named in the DAT |
| Source Schema Name | DAT | `{catalog}.{schema}` from the DAT physical table |
| Source Table Name | DAT | Physical (Technical) Table Name column from DAT |
| Source Column | DAT | Physical Attribute Name column from DAT |

## Target Columns — Populate from DAT + DRD

| STTM Field | Source | Value |
|-----------|--------|-------|
| Target Data Lake | DAT | `catalog.schema` (e.g., `{target_catalog}.{target_schema}`) |
| Target Table Name | DAT | PascalCase table name derived from DAT logical table name |
| Target Column | DRD | PascalCase conversion of DRD attribute name, ending with approved class word |
| Target Data Type | DAT | `string`, `int`, `decimal(18,3)`, `timestamp`, etc. — from DAT source data type |
| Allow Nulls | DRD | `NOT NULL` if DRD data quality expectation mandates non-null; otherwise `NULL` |
| Merge Key | DRD | `Yes` if attribute is part of the merge/upsert key defined in DRD |
| Primary Key | DRD | `Yes` if PK (must include your project's scoping identifiers, e.g. `SourceSystemId` + `ReportingUnitId`) |
| Data Transformation Rules | DRD | `Direct` / `CAST` / `CASE WHEN` / derived logic from DRD transformation rules |
| Column Description | DRD | Business definition from DRD Subject Area Attribute Description column |
| Version | — | Always `V1` |

## Mandatory Audit Columns

Append these at the end of every table in the STTM. Rename to match your project's existing audit-column convention if one is already defined (e.g. `XTNDFSystemId` instead of `SourceSystemId`).

| Target Column | Data Type | Allow Nulls | Notes |
|--------------|-----------|------------|-------|
| `MarketCode` | `string` | NOT NULL | Market/region scope identifier (optional \u2014 only if project scopes by market) |
| `SourceSystemId` | `int` | NOT NULL | PK \u2014 value from spec |
| `ReportingUnitId` | `int` | NOT NULL | PK \u2014 value from spec |
| `CreatedTimestamp` | `timestamp` | NOT NULL | `CURRENT_TIMESTAMP()` |
| `CreatedBy` | `string` | NOT NULL | `current_user()` |
| `UpdatedTimestamp` | `timestamp` | NOT NULL | `CURRENT_TIMESTAMP()` |
| `UpdatedBy` | `string` | NOT NULL | `current_user()` |

## Common View Consistency

> **Critical**: Never mix view name into the Data Lake column, or schema name into the Common ViewName column. Every row must have identical values for `Data Lake` and `Common ViewName` across all rows in the STTM.

- `Data Lake` (col 26) = `catalog.schema_vw` (e.g., `{target_catalog}.{target_schema}_vw`)
- `Common ViewName` (col 27) = `TableName_vw`
- `Common View Column Name` (col 28) = same as `Target Column` (col 15)
