# Reference: T-SQL (Azure SQL) → Spark/Delta type mapping

Used by the Migration Architect when the run's source type is `azuresql`, to fill the `type_mapping` section of `source-to-target-mapping.yaml`. Record every mapping explicitly in the mapping file; never leave a type implicit.

| T-SQL type | Spark / Delta type | Notes |
|---|---|---|
| `bit` | `BOOLEAN` | |
| `tinyint`, `smallint` | `SMALLINT` (tinyint → `SMALLINT`, since Spark TINYINT is signed) | |
| `int` | `INT` | |
| `bigint` | `BIGINT` | |
| `decimal(p,s)`, `numeric(p,s)` | `DECIMAL(p,s)` | Spark max precision 38 — flag anything larger |
| `money` | `DECIMAL(19,4)` | `smallmoney` → `DECIMAL(10,4)` |
| `float` | `DOUBLE` | `real` → `FLOAT` |
| `char(n)`, `varchar(n)`, `nchar(n)`, `nvarchar(n)`, `text`, `ntext` | `STRING` | length lost; keep a length check as a DQ rule if the source length matters |
| `date` | `DATE` | |
| `datetime`, `datetime2`, `smalldatetime` | `TIMESTAMP` | `datetime` has ~3 ms precision; note rounding |
| `datetimeoffset` | `TIMESTAMP` | offset normalized to UTC — flag it in the blueprint |
| `time` | `STRING` | Spark has no TIME type; cast later if needed |
| `uniqueidentifier` | `STRING` | |
| `binary`, `varbinary`, `image` | `BINARY` | |
| `xml` | `STRING` | |
| `rowversion`/`timestamp` | `BINARY` | not a datetime despite the name; exclude from business columns |
| `sql_variant`, `geography`, `geometry`, `hierarchyid` | **unsupported** | list as `no_mapping` with a risk entry in the assessment; ask the user how to handle |

Also record: nullable columns, identity columns (`IDENTITY` is not carried; the PK stays as a plain key), computed columns (load the computed value, not the expression), and collation differences (Spark string comparison is case-sensitive; a case-insensitive source collation is a risk for dedup/join keys — flag it).
