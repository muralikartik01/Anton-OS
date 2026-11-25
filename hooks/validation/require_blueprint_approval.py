#!/usr/bin/env python3
"""PreToolUse hook: block execute_statement until the migration blueprint is approved.

Matches mcp__db-kit-databricks__execute_statement (any other tool passes through).
Reads tool_input.run_id, loads observability/run-records/<run_id>.yaml, and
requires an `approvals` entry with stage `migration_blueprint`. This is spec
section 11 Stage 4 enforced rather than merely documented (mechanism type C,
workflow-state gate -- same pattern as require_validation_complete.py).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

REPO_ROOT = Path(__file__).resolve().parents[2]
GATED_TOOL = "mcp__db-kit-databricks__execute_statement"
APPROVAL_STAGE = "migration_blueprint"
RUN_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")  # no path separators: run_id becomes a filename


def main() -> int:
    payload = json.load(sys.stdin)
    if payload.get("tool_name") != GATED_TOOL:
        return 0

    run_id = str(payload.get("tool_input", {}).get("run_id", "")).strip()
    if not run_id or run_id in {".", ".."} or not RUN_ID_RE.match(run_id):
        print("blocked: execute_statement requires a valid run_id (letters, digits, . _ -).", file=sys.stderr)
        return 2

    record_path = REPO_ROOT / "observability" / "run-records" / f"{run_id}.yaml"
    if yaml is None or not record_path.exists():
        print(f"blocked: no run record at {record_path}; cannot verify blueprint approval.", file=sys.stderr)
        return 2

    record = yaml.safe_load(record_path.read_text()) or {}
    approvals = record.get("approvals") or []
    if any(isinstance(a, dict) and a.get("stage") == APPROVAL_STAGE for a in approvals):
        return 0

    print(
        f"blocked: run '{run_id}' has no '{APPROVAL_STAGE}' approval in its run record. "
        "A human must approve the blueprint (Stage 4) before any statement executes.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
