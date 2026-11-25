"""db-kit-azuresql MCP server -- REAL, READ-ONLY connector to an Azure SQL Database source.

Contract: integrations/mcp/azuresql/CONTRACT.md
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

from tsql_guard import is_read_only, validate_identifier  # noqa: E402

REQUIRED_ENV = ("DB_KIT_AZSQL_SERVER", "DB_KIT_AZSQL_DATABASE", "DB_KIT_AZSQL_USER", "DB_KIT_AZSQL_PASSWORD")

server = MCPServer(
    name="db-kit-azuresql",
    description="Read-only Azure SQL Database source connector for DB-Kit (discovery and profiling).",
)


def _connect():
    missing = [v for v in REQUIRED_ENV if not os.environ.get(v)]
    if missing:
        raise RuntimeError(f"missing required environment variables: {', '.join(missing)} (see .env.example)")
    import pymssql  # imported lazily so the module loads without the driver for tests

    return pymssql.connect(
        server=os.environ["DB_KIT_AZSQL_SERVER"],
        user=os.environ["DB_KIT_AZSQL_USER"],
        password=os.environ["DB_KIT_AZSQL_PASSWORD"],
        database=os.environ["DB_KIT_AZSQL_DATABASE"],
        port=os.environ.get("DB_KIT_AZSQL_PORT", "1433"),
        login_timeout=30,
        timeout=300,
        autocommit=False,  # pymssql has no read-only flag; nothing is ever committed (see _run) and tsql_guard rejects non-SELECT
    )


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
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME",
            (sch,),
        )
    except Exception as exc:
        return {"tables": [], "error": str(exc)}
    return {"tables": [r[0] for r in res["rows"]]}


@server.tool()
def describe_table(schema: str, table: str) -> dict[str, Any]:
    """Columns (name, T-SQL type, length/precision/scale, nullable, ordinal), primary key and foreign keys."""
    sch, tbl = validate_identifier(schema, "schema"), validate_identifier(table, "table")
    try:
        cols = _run(
            "SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE, IS_NULLABLE, ORDINAL_POSITION "
            "FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s ORDER BY ORDINAL_POSITION",
            (sch, tbl),
        )
        pks = _run(
            "SELECT k.COLUMN_NAME FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS c "
            "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE k ON c.CONSTRAINT_NAME = k.CONSTRAINT_NAME AND c.TABLE_SCHEMA = k.TABLE_SCHEMA "
            "WHERE c.CONSTRAINT_TYPE = 'PRIMARY KEY' AND c.TABLE_SCHEMA = %s AND c.TABLE_NAME = %s ORDER BY k.ORDINAL_POSITION",
            (sch, tbl),
        )
        fks = _run(
            "SELECT cu.COLUMN_NAME, pk.TABLE_SCHEMA, pk.TABLE_NAME, pt.COLUMN_NAME "
            "FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc "
            "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE cu ON rc.CONSTRAINT_NAME = cu.CONSTRAINT_NAME "
            "JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS pk ON rc.UNIQUE_CONSTRAINT_NAME = pk.CONSTRAINT_NAME "
            "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE pt ON pk.CONSTRAINT_NAME = pt.CONSTRAINT_NAME "
            "WHERE cu.TABLE_SCHEMA = %s AND cu.TABLE_NAME = %s",
            (sch, tbl),
        )
    except Exception as exc:
        return {"columns": [], "primary_key_columns": [], "foreign_keys": [], "error": str(exc)}
    if not cols["rows"]:
        return {"columns": [], "primary_key_columns": [], "foreign_keys": [], "error": f"table '{sch}.{tbl}' not found"}
    return {
        "columns": [
            {"column": r[0], "data_type": r[1], "char_max_length": r[2], "numeric_precision": r[3], "numeric_scale": r[4],
             "is_nullable": r[5], "ordinal_position": r[6]}
            for r in cols["rows"]
        ],
        "primary_key_columns": [r[0] for r in pks["rows"]],
        "foreign_keys": [{"column": r[0], "references_schema": r[1], "references_table": r[2], "references_column": r[3]} for r in fks["rows"]],
    }


@server.tool()
def execute_sql_read_only(sql: str, row_limit: int = 1000) -> dict[str, Any]:
    """Run exactly one read-only T-SQL SELECT/WITH query (no INTO, EXEC or DML anywhere) and return rows."""
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
