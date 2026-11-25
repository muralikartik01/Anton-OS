#!/usr/bin/env python3
"""PreToolUse hook: block writing a final report until validation results are complete.

Matches Write on a path matching artifacts/reports/**/*-report.md. Looks for
a sibling results.md under artifacts/validation/<project-id>/<run-id>/ for
the same run-id in the path, and requires every rule row in it to carry an
explicit status (pass/fail/blocked) -- no silent omissions. This is the
Stage 6 -> Stage 7 gate from the gap-resolutions design doc §2.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH_RE = re.compile(r"artifacts/reports/(?P<project_id>[^/]+)/(?P<run_id>[^/]+)/.*-report\.md$")
STATUS_RE = re.compile(r"\b(pass|fail|blocked)\b", re.IGNORECASE)


def main() -> int:
    payload = json.load(sys.stdin)
    file_path = payload.get("tool_input", {}).get("file_path", "")
    match = REPORT_PATH_RE.search(file_path.replace("\\", "/"))
    if not match:
        return 0  # not a final-report write; nothing to gate

    results_path = REPO_ROOT / "artifacts" / "validation" / match["project_id"] / match["run_id"] / "results.md"
    if not results_path.exists():
        print(f"blocked: no validation results found at {results_path}. Run validation before writing the report.", file=sys.stderr)
        return 2

    lines = [l for l in results_path.read_text().splitlines() if l.strip().startswith("|")][2:]  # skip md table header/divider
    if not lines:
        print(f"blocked: {results_path} has no rule rows to evaluate.", file=sys.stderr)
        return 2

    missing_status = [l for l in lines if not STATUS_RE.search(l)]
    if missing_status:
        print(
            f"blocked: {len(missing_status)} row(s) in {results_path} have no explicit pass/fail/blocked status.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
