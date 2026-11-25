#!/usr/bin/env python3
"""PreToolUse hook: block destructive-SQL keyword patterns unless approved.

Matches Bash and mcp__.* (scans every string value in tool_input, so a `sql`
parameter on an MCP call is covered). Pattern/keyword-based only -- not a semantic guarantee, see
rules/security/safety-boundaries.md and the gap-resolutions design doc §2.
Override requires DB_KIT_DESTRUCTIVE_APPROVED=1 to be set by a human in the
shell session; an agent cannot set this for itself.
"""
from __future__ import annotations

import json
import os
import re
import sys

DESTRUCTIVE_PATTERNS = [
    r"(?i)\bDROP\s+(TABLE|DATABASE|SCHEMA|INDEX|VIEW)\b",
    r"(?i)\bTRUNCATE\s+TABLE\b",
    r"(?i)\bDELETE\s+FROM\s+\S+\s*(;|$)",  # DELETE with no WHERE clause before end-of-statement
    r"(?i)\bALTER\s+TABLE\s+\S+\s+DROP\s+COLUMN\b",
]


def extract_text(value) -> str:
    """Concatenate every string value found anywhere in a tool_input structure."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(extract_text(v) for v in value.values())
    if isinstance(value, list):
        return "\n".join(extract_text(v) for v in value)
    return ""


def main() -> int:
    payload = json.load(sys.stdin)
    command = extract_text(payload.get("tool_input", {}))

    for pattern in DESTRUCTIVE_PATTERNS:
        if re.search(pattern, command):
            if os.environ.get("DB_KIT_DESTRUCTIVE_APPROVED") == "1":
                return 0
            print(
                "blocked: command matches a destructive-SQL pattern and "
                "DB_KIT_DESTRUCTIVE_APPROVED=1 is not set. A human must set "
                "that environment variable after reviewing the statement.",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
