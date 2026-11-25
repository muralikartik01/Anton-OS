"""db-kit-databricks MCP server -- REAL connector to a live Databricks SQL warehouse.

Contract: integrations/mcp/databricks-sql/CONTRACT.md
Credentials come only from environment variables (see .env.example); nothing is hardcoded.

Run with: python3 server.py   (stdio transport)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from sql_guard import is_read_only, quote_ident, validate_identifier  # noqa: E402

REQUIRED_ENV = ("DB_KIT_DBX_HOST", "DB_KIT_DBX_HTTP_PATH", "DB_KIT_DBX_TOKEN")

server = MCPServer(
    name="db-kit-databricks",
    description="Real Databricks SQL / Unity Catalog connector for DB-Kit (profiling, validation, Bronze/Silver DDL/DML).",
)


def _connect():
    missing = [v for v in REQUIRED_ENV if not os.environ.get(v)]
    if missing:
        raise RuntimeError(f"missing required environment variables: {', '.join(missing)} (see .env.example)")
    from databricks import sql  # imported lazily so the module loads without the driver for tests

    return sql.connect(
        server_hostname=os.environ["DB_KIT_DBX_HOST"],
        http_path=os.environ["DB_KIT_DBX_HTTP_PATH"],
        access_token=os.environ["DB_KIT_DBX_TOKEN"],
    )


def _run(sql_text: str, row_limit: int | None = None) -> dict[str, Any]:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql_text)
        if cur.description is None:
            return {"columns": [], "rows": [], "row_count": 0, "truncated": False}
        columns = [d[0] for d in cur.description]
        if row_limit is None:
            fetched = cur.fetchall()
            truncated = False
        else:
            fetched = cur.fetchmany(row_limit + 1)
            truncated = len(fetched) > row_limit
            fetched = fetched[:row_limit]
        rows = [[None if v is None else (v if isinstance(v, (int, float, bool, str)) else str(v)) for v in r] for r in fetched]
        return {"columns": columns, "rows": rows, "row_count": len(rows), "truncated": truncated}


@server.tool()
def list_tables(catalog: str, schema: str) -> dict[str, Any]:
    """List tables in catalog.schema. Returns {"tables": [name,...]} or {"tables": [], "error": ...}."""
    cat, sch = validate_identifier(catalog, "catalog"), validate_identifier(schema, "schema")
    try:
        res = _run(f"SHOW TABLES IN {quote_ident(cat)}.{quote_ident(sch)}")
    except Exception as exc:  # surface the real error, never guess
        return {"tables": [], "error": str(exc)}
    idx = res["columns"].index("tableName") if "tableName" in res["columns"] else 1
    return {"tables": sorted(r[idx] for r in res["rows"])}


@server.tool()
def describe_table(catalog: str, schema: str, table: str) -> dict[str, Any]:
    """Columns (name, type, nullable, comment, ordinal) and primary-key columns for catalog.schema.table."""
    cat, sch, tbl = (validate_identifier(catalog, "catalog"), validate_identifier(schema, "schema"), validate_identifier(table, "table"))
    try:
        cols = _run(
            f"SELECT column_name, data_type, is_nullable, comment, ordinal_position "
            f"FROM {quote_ident(cat)}.information_schema.columns "
            f"WHERE table_schema = '{sch}' AND table_name = '{tbl}' ORDER BY ordinal_position"
        )
        pks = _run(
            f"SELECT kcu.column_name FROM {quote_ident(cat)}.information_schema.table_constraints tc "
            f"JOIN {quote_ident(cat)}.information_schema.key_column_usage kcu "
            f"ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema "
            f"WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = '{sch}' AND tc.table_name = '{tbl}' "
            f"ORDER BY kcu.ordinal_position"
        )
    except Exception as exc:
        return {"columns": [], "primary_key_columns": [], "error": str(exc)}
    if not cols["rows"]:
        return {"columns": [], "primary_key_columns": [], "error": f"table '{cat}.{sch}.{tbl}' not found"}
    return {
        "columns": [
            {"column": r[0], "data_type": r[1], "is_nullable": r[2], "comment": r[3], "ordinal_position": r[4]} for r in cols["rows"]
        ],
        "primary_key_columns": [r[0] for r in pks["rows"]],
    }


@server.tool()
def execute_sql_read_only(sql: str, row_limit: int = 1000) -> dict[str, Any]:
    """Run a read-only statement (SELECT/WITH/DESCRIBE/SHOW/EXPLAIN, single statement) and return rows."""
    if not is_read_only(sql):
        return {"status": "rejected", "reason": "only a single SELECT/WITH/DESCRIBE/SHOW/EXPLAIN statement is allowed"}
    if row_limit < 1 or row_limit > 100000:
        return {"status": "rejected", "reason": "row_limit must be between 1 and 100000"}
    try:
        return {"status": "ok", **_run(sql, row_limit)}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


@server.tool()
def execute_statement(sql: str, run_id: str, confirm: bool = False) -> dict[str, Any]:
    """Run one DDL/DML statement. Needs confirm=True; hooks additionally require an approved blueprint for run_id."""
    if confirm is not True:
        return {"status": "rejected", "reason": "confirm must be true for a write statement"}
    if not run_id:
        return {"status": "rejected", "reason": "run_id is required"}
    from sql_guard import has_multiple_statements

    if has_multiple_statements(sql):
        return {"status": "rejected", "reason": "exactly one statement per call"}
    try:
        res = _run(sql)
        affected = res["rows"][0][0] if res["rows"] and res["columns"] and res["columns"][0].startswith("num_") else None
        return {"status": "executed", "rows_affected": affected, "error": None}
    except Exception as exc:
        return {"status": "failed", "rows_affected": None, "error": str(exc)}


if __name__ == "__main__":
    server.run("stdio")
