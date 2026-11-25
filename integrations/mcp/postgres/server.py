"""db-kit-postgres MCP server -- REAL, READ-ONLY connector to an Azure Database for PostgreSQL source.

Contract: integrations/mcp/postgres/CONTRACT.md
Credentials come only from environment variables (see .env.example). There is deliberately
no write tool: DB-Kit reads this source; data reaches Databricks through the approved
landing_load statements executed on the Databricks side.

Run with: python3 server.py   (stdio transport)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from pg_guard import is_read_only, validate_identifier  # noqa: E402

REQUIRED_ENV = ("DB_KIT_PG_HOST", "DB_KIT_PG_DATABASE", "DB_KIT_PG_USER", "DB_KIT_PG_PASSWORD")

server = MCPServer(
    name="db-kit-postgres",
    description="Read-only Azure Database for PostgreSQL source connector for DB-Kit (discovery and profiling).",
)


def _connect():
    missing = [v for v in REQUIRED_ENV if not os.environ.get(v)]
    if missing:
        raise RuntimeError(f"missing required environment variables: {', '.join(missing)} (see .env.example)")
    import psycopg  # imported lazily so the module loads without the driver for tests

    conn = psycopg.connect(
        host=os.environ["DB_KIT_PG_HOST"],
        port=os.environ.get("DB_KIT_PG_PORT", "5432"),
        dbname=os.environ["DB_KIT_PG_DATABASE"],
        user=os.environ["DB_KIT_PG_USER"],
        password=os.environ["DB_KIT_PG_PASSWORD"],
        sslmode=os.environ.get("DB_KIT_PG_SSLMODE", "require"),
        connect_timeout=30,
        options="-c statement_timeout=300000",
    )
    conn.read_only = True  # session-level read-only: the server itself rejects writes
    return conn


def _jsonable(v: Any) -> Any:
    return v if v is None or isinstance(v, (int, float, bool, str)) else str(v)


def _run(sql_text: str, params: tuple = (), row_limit: int | None = None) -> dict[str, Any]:
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(sql_text, params) if params else cur.execute(sql_text)
        if cur.description is None:
            return {"columns": [], "rows": [], "row_count": 0, "truncated": False}
        columns = [d[0] for d in cur.description]
        if row_limit is None:
            fetched, truncated = cur.fetchall(), False
        else:
            fetched = cur.fetchmany(row_limit + 1)
            truncated = len(fetched) > row_limit
            fetched = fetched[:row_limit]
        return {"columns": columns, "rows": [[_jsonable(v) for v in r] for r in fetched], "row_count": len(fetched), "truncated": truncated}
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


@server.tool()
def list_tables(schema: str) -> dict[str, Any]:
    """List base tables in a schema of the configured database. Returns {"tables": [...]} or {"tables": [], "error": ...}."""
    sch = validate_identifier(schema, "schema")
    try:
        res = _run(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = %s AND table_type = 'BASE TABLE' ORDER BY table_name",
            (sch,),
        )
    except Exception as exc:
        return {"tables": [], "error": str(exc)}
    return {"tables": [r[0] for r in res["rows"]]}


@server.tool()
def describe_table(schema: str, table: str) -> dict[str, Any]:
    """Columns (name, PostgreSQL type, length/precision/scale, nullable, ordinal), primary key and foreign keys."""
    sch, tbl = validate_identifier(schema, "schema"), validate_identifier(table, "table")
    try:
        cols = _run(
            "SELECT column_name, data_type, character_maximum_length, numeric_precision, numeric_scale, is_nullable, ordinal_position, udt_name "
            "FROM information_schema.columns WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
            (sch, tbl),
        )
        pks = _run(
            "SELECT k.column_name FROM information_schema.table_constraints c "
            "JOIN information_schema.key_column_usage k ON c.constraint_name = k.constraint_name AND c.table_schema = k.table_schema AND c.table_name = k.table_name "
            "WHERE c.constraint_type = 'PRIMARY KEY' AND c.table_schema = %s AND c.table_name = %s ORDER BY k.ordinal_position",
            (sch, tbl),
        )
        fks = _run(
            "SELECT k.column_name, ccu.table_schema, ccu.table_name, ccu.column_name "
            "FROM information_schema.table_constraints c "
            "JOIN information_schema.key_column_usage k ON c.constraint_name = k.constraint_name AND c.table_schema = k.table_schema AND c.table_name = k.table_name "
            "JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = c.constraint_name AND ccu.constraint_schema = c.table_schema "
            "WHERE c.constraint_type = 'FOREIGN KEY' AND c.table_schema = %s AND c.table_name = %s",
            (sch, tbl),
        )
    except Exception as exc:
        return {"columns": [], "primary_key_columns": [], "foreign_keys": [], "error": str(exc)}
    if not cols["rows"]:
        return {"columns": [], "primary_key_columns": [], "foreign_keys": [], "error": f"table '{sch}.{tbl}' not found"}
    return {
        "columns": [
            {"column": r[0], "data_type": r[1], "char_max_length": r[2], "numeric_precision": r[3], "numeric_scale": r[4],
             "is_nullable": r[5], "ordinal_position": r[6], "udt_name": r[7]}
            for r in cols["rows"]
        ],
        "primary_key_columns": [r[0] for r in pks["rows"]],
        "foreign_keys": [{"column": r[0], "references_schema": r[1], "references_table": r[2], "references_column": r[3]} for r in fks["rows"]],
    }


@server.tool()
def execute_sql_read_only(sql: str, row_limit: int = 1000) -> dict[str, Any]:
    """Run exactly one read-only PostgreSQL SELECT/WITH query (no INTO, EXEC or DML anywhere) and return rows."""
    if not is_read_only(sql):
        return {"status": "rejected", "reason": "only a single read-only SELECT/WITH statement is allowed (no INTO, EXEC, DML or DDL)"}
    if row_limit < 1 or row_limit > 100000:
        return {"status": "rejected", "reason": "row_limit must be between 1 and 100000"}
    try:
        return {"status": "ok", **_run(sql, row_limit=row_limit)}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


if __name__ == "__main__":
    server.run("stdio")
