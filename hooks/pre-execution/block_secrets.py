#!/usr/bin/env python3
"""PreToolUse hook: block writes/commands containing secret-shaped strings.

Matches Write, Edit, Bash. Reads the Claude Code hook JSON payload from
stdin; exits 2 (block) with a reason on stderr if a credential-shaped
pattern is found, 0 (allow) otherwise. Pattern-based, not a guarantee --
see rules/security/safety-boundaries.md.
"""
from __future__ import annotations

import json
import re
import sys

PATTERNS = [
    (r"AKIA[0-9A-Z]{16}", "AWS access key id"),
    (r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----", "private key block"),
    (r"(?i)(password|passwd|pwd)\s*[=:]\s*['\"][^'\"\s]{4,}['\"]", "hardcoded password literal"),
    (r"(?i)(secret|api[_-]?key|access[_-]?token)\s*[=:]\s*['\"][A-Za-z0-9/+_\-]{12,}['\"]", "hardcoded secret/token literal"),
    (r"(?i)://[^:\s]+:[^@\s]{4,}@", "credential embedded in a connection URL"),
]


def extract_text(payload: dict) -> str:
    tool_input = payload.get("tool_input", {})
    return " ".join(str(v) for v in tool_input.values() if isinstance(v, str))


def main() -> int:
    payload = json.load(sys.stdin)
    text = extract_text(payload)
    for pattern, label in PATTERNS:
        if re.search(pattern, text):
            print(f"blocked: content matches secret pattern ({label}). Remove the credential before writing.", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
