#!/usr/bin/env python3
"""PreToolUse hook: block writes/commands targeting a connection tagged production.

Matches Bash and mcp__.* (scans every string value in tool_input). Reads config/integrations.yaml; for any connection with
production: true, blocks a command referencing that connection's type
unless DB_KIT_PRODUCTION_WRITE_APPROVED=1 is set by a human. In this pilot
both declared connections are non-production, so this hook is a real gate
with nothing to currently trip -- it activates the moment a production
connection is added to integrations.yaml.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

REPO_ROOT = Path(__file__).resolve().parents[2]
INTEGRATIONS_PATH = REPO_ROOT / "config" / "integrations.yaml"


def production_connection_markers() -> list[str]:
    if yaml is None or not INTEGRATIONS_PATH.exists():
        return []
    data = yaml.safe_load(INTEGRATIONS_PATH.read_text()) or {}
    connections = data.get("connections", {})
    return [
        str(conn.get("type", name))
        for name, conn in connections.items()
        if isinstance(conn, dict) and conn.get("production") is True
    ]


def extract_text(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(extract_text(v) for v in value.values())
    if isinstance(value, list):
        return "\n".join(extract_text(v) for v in value)
    return ""


def production_mcp_server(tool_name: str) -> bool:
    """True if tool_name is mcp__<server>__<op> and <server> is declared production: true."""
    parts = tool_name.split("__")
    if len(parts) < 3 or parts[0] != "mcp" or yaml is None or not INTEGRATIONS_PATH.exists():
        return False
    data = yaml.safe_load(INTEGRATIONS_PATH.read_text()) or {}
    server = (data.get("mcp") or {}).get(parts[1]) or {}
    return server.get("production") is True


def main() -> int:
    payload = json.load(sys.stdin)
    command = extract_text(payload.get("tool_input", {}))

    if production_mcp_server(payload.get("tool_name", "")):
        if os.environ.get("DB_KIT_PRODUCTION_WRITE_APPROVED") != "1":
            print(
                "blocked: this MCP server is declared production: true in config/integrations.yaml "
                "and DB_KIT_PRODUCTION_WRITE_APPROVED=1 is not set.",
                file=sys.stderr,
            )
            return 2

    for marker in production_connection_markers():
        if marker and marker.lower() in command.lower():
            if os.environ.get("DB_KIT_PRODUCTION_WRITE_APPROVED") == "1":
                return 0
            print(
                f"blocked: command references the production-tagged connection '{marker}' "
                "and DB_KIT_PRODUCTION_WRITE_APPROVED=1 is not set.",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
