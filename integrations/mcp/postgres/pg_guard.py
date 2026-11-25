"""Pure PostgreSQL text helpers for the db-kit-postgres connector (no I/O, unit-testable).

The connector is READ-ONLY by design. PostgreSQL has several ways a statement that
*starts* with SELECT/WITH can still write (SELECT ... INTO, WITH ... DELETE,
side-effect functions), so the guard scans every token, not just the first one.
The connection is ALSO opened read-only at the session level (defence in depth).
"""
from __future__ import annotations

import re

WRITE_KEYWORDS = {
    "insert", "update", "delete", "merge", "into", "drop", "create", "alter", "truncate", "grant", "revoke",
    "copy", "call", "do", "execute", "prepare", "vacuum", "analyze", "set", "reset", "lock", "listen", "notify",
    "refresh", "reindex", "cluster", "comment", "security", "load",
    # side-effect / file / network functions reachable from a plain SELECT
    "set_config", "nextval", "setval", "pg_read_file", "pg_read_binary_file", "pg_ls_dir", "pg_terminate_backend",
    "pg_cancel_backend", "lo_import", "lo_export", "lo_unlink", "dblink", "dblink_exec", "pg_advisory_lock",
}
_IDENT_RE = re.compile(r"^[A-Za-z0-9_\-]+$")
_STRING_RE = re.compile(r"'(?:[^']|'')*'")
_DOLLAR_RE = re.compile(r"\$([A-Za-z_]*)\$.*?\$\1\$", re.DOTALL)
_QUOTED_IDENT_RE = re.compile(r'"(?:[^"]|"")*"')
_LINE_COMMENT_RE = re.compile(r"--[^\n]*")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


def _sanitize(sql: str) -> str:
    """Remove comments, string literals (incl. $$ quoting) and "quoted identifiers" so keyword scans see only code."""
    s = _BLOCK_COMMENT_RE.sub(" ", sql)
    s = _LINE_COMMENT_RE.sub(" ", s)
    s = _DOLLAR_RE.sub("''", s)
    s = _STRING_RE.sub("''", s)
    return _QUOTED_IDENT_RE.sub('""', s)


def has_multiple_statements(sql: str) -> bool:
    s = _sanitize(sql).strip()
    idx = s.find(";")
    return idx != -1 and bool(s[idx + 1:].strip())


def is_read_only(sql: str) -> bool:
    s = _sanitize(sql).strip()
    if not s or has_multiple_statements(sql):
        return False
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", s)
    if not tokens or tokens[0].lower() not in ("select", "with"):
        return False
    return not any(t.lower() in WRITE_KEYWORDS for t in tokens)


def validate_identifier(name: str, what: str) -> str:
    if not isinstance(name, str) or not _IDENT_RE.match(name):
        raise ValueError(f"invalid {what} '{name}': only letters, digits, underscore and hyphen allowed")
    return name
