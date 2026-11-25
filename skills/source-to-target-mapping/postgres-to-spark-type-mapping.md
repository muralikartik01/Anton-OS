# Reference: PostgreSQL → Spark/Delta type mapping

Used by the Migration Architect when the run's source type is `postgres`, to fill the `type_mapping` section of `source-to-target-mapping.yaml`. Record every mapping explicitly; never leave a type implicit. `describe_table` returns `data_type` and `udt_name` — use `udt_name` for arrays and user-defined types.

| PostgreSQL type | Spark / Delta type | Notes |
|---|---|---|
| `boolean` | `BOOLEAN` | |
| `smallint`, `int2` | `SMALLINT` | |
| `integer`, `int4` | `INT` | |
| `bigint`, `int8` | `BIGINT` | |
| `serial`/`bigserial` | `INT` / `BIGINT` | the sequence default is not carried; the PK stays a plain key |
| `numeric(p,s)`, `decimal(p,s)` | `DECIMAL(p,s)` | unconstrained `numeric` has no fixed precision — flag it and pick `DECIMAL(38,18)` only with approval; max precision 38 |
| `money` | `DECIMAL(19,2)` | locale-dependent in the source — flag it |
| `real`, `float4` | `FLOAT` | |
| `double precision`, `float8` | `DOUBLE` | |
| `char(n)`, `varchar(n)`, `text`, `citext` | `STRING` | length lost; keep a length check as a DQ rule if it matters. `citext` is case-insensitive in the source, Spark strings are not — flag for dedup/join keys |
| `date` | `DATE` | |
| `timestamp` (without time zone) | `TIMESTAMP_NTZ` | |
| `timestamptz` | `TIMESTAMP` | normalized to UTC — flag it in the blueprint |
| `time`, `timetz`, `interval` | `STRING` | no Spark equivalent; cast later if needed |
| `uuid` | `STRING` | |
| `bytea` | `BINARY` | |
| `json`, `jsonb` | `STRING` | parse in Silver with `from_json` only if a schema is agreed |
| `xml` | `STRING` | |
| `inet`, `cidr`, `macaddr` | `STRING` | |
| arrays (`udt_name` starting `_`) | `ARRAY<element type>` | map the element type with this table; flag as a risk |
| `enum` types | `STRING` | list the allowed values as a DQ `matches_set` rule |
| `geometry`, `geography` (PostGIS), `hstore`, range types, composite types | **unsupported** | list as `no_mapping` with a risk entry in the assessment; ask the user how to handle |

Also record: nullable columns, identity/serial defaults (not carried), generated columns (load the value, not the expression), and Postgres's lower-casing of unquoted identifiers (keep names exactly as `describe_table` returns them).
