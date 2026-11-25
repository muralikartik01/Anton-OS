# DDL Generation Rules

## CREATE TABLE Template

Always generate `CREATE TABLE IF NOT EXISTS` (no live DB connection — no ALTER logic):

```sql
CREATE TABLE IF NOT EXISTS catalog.schema.TableName (
    ColumnName    data_type    NOT NULL  COMMENT 'Column description',
    -- ... all business columns from STTM ...
    MarketCode              string      NOT NULL  COMMENT 'Market/region scope identifier',
    SourceSystemId          int         NOT NULL  COMMENT 'Source system identifier',
    ReportingUnitId         int         NOT NULL  COMMENT 'Reporting unit identifier',
    CreatedTimestamp        timestamp   NOT NULL  COMMENT 'Record creation timestamp',
    CreatedBy               string      NOT NULL  COMMENT 'Created by user/process',
    UpdatedTimestamp        timestamp   NOT NULL  COMMENT 'Last update timestamp',
    UpdatedBy               string      NOT NULL  COMMENT 'Updated by user/process'
)
USING DELTA
PARTITIONED BY (SourceSystemId, ReportingUnitId)
COMMENT 'Table description from spec'
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact'   = 'true'
);
```

Rename the audit columns above to match your project's existing convention if one is already defined (e.g. `XTNDFSystemId` instead of `SourceSystemId`).

## Partitioning Strategy

Use volume estimate from spec to determine partition columns:

| Volume | Partition columns |
|--------|------------------|
| < 1M rows | `SourceSystemId`, `ReportingUnitId` |
| 1M – 100M rows | + a business date column (e.g., `DocumentPostingDate`) |
| > 100M rows | + date + high-cardinality business key |

Apply `ZORDER BY` for frequently filtered/joined columns identified in the spec's query patterns.

## Common View

Append after the CREATE TABLE:

```sql
CREATE OR REPLACE VIEW catalog.schema_vw.TableName_vw AS
SELECT * FROM catalog.schema.TableName;
```

Common View schema: append `_vw` to the base schema (e.g., `{target_catalog}.{target_schema}_vw`), or use your project's own suffix convention.
