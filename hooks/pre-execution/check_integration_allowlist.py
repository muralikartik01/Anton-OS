#!/usr/bin/env python3
"""PreToolUse hook: block MCP tool calls not declared in config/integrations.yaml.

Matches mcp__db-kit-context__* (and any future mcp__* tool). Looks up the
server's allowed_operations list in integrations.yaml and blocks anything
not on it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

REPO_ROOT = Path(__file__).resolve().parents[2]
INTEGRATIONS_PATH = REPO_ROOT / "config" / "integrations.yaml"


def allowed_operations(server_key: str) -> list[str] | None:
    if yaml is None or not INTEGRATIONS_PATH.exists():
        return None
    data = yaml.safe_load(INTEGRATIONS_PATH.read_text()) or {}
    server = data.get("mcp", {}).get(server_key)
    if not server:
        return None
    return server.get("allowed_operations")


def main() -> int:
    payload = json.load(sys.stdin)
    tool_name = payload.get("tool_name", "")
    if not tool_name.startswith("mcp__"):
        return 0

    parts = tool_name.split("__")
    if len(parts) < 3:
        return 0
    server_key, operation = parts[1], parts[2]

    allowed = allowed_operations(server_key)
    if allowed is None:
        print(f"blocked: MCP server '{server_key}' is not declared in config/integrations.yaml.", file=sys.stderr)
        return 2
    if operation not in allowed:
        print(f"blocked: operation '{operation}' is not in {server_key}'s allowed_operations.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
