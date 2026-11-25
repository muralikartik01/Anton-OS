"""Pure SQL-text helpers for the db-kit-databricks connector (no I/O, unit-testable)."""
from __future__ import annotations

import re

READ_ONLY_STARTS = ("select", "with", "describe", "show", "explain")
_IDENT_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def strip_leading_comments(sql: str) -> str:
    s = sql.lstrip()
    while True:
        if s.startswith("--"):
            s = s.split("\n", 1)[1].lstrip() if "\n" in s else ""
        elif s.startswith("/*"):
            end = s.find("*/")
            s = s[end + 2:].lstrip() if end != -1 else ""
        else:
            return s


def has_multiple_statements(sql: str) -> bool:
    """True if a ';' is followed by anything other than whitespace/comments (outside string literals)."""
    in_str, quote, i = False, "", 0
    while i < len(sql):
        ch = sql[i]
        if in_str:
            if ch == quote:
                in_str = False
        elif ch in ("'", '"', "`"):
            in_str, quote = True, ch
        elif ch == ";":
            return bool(strip_leading_comments(sql[i + 1:]).strip())
        i += 1
    return False


def is_read_only(sql: str) -> bool:
    body = strip_leading_comments(sql)
    if not body or has_multiple_statements(sql):
        return False
    return body.split(None, 1)[0].lower().rstrip("(") in READ_ONLY_STARTS


def validate_identifier(name: str, what: str) -> str:
    """Catalog/schema/table names are interpolated into SHOW/DESCRIBE; allow only safe characters."""
    if not isinstance(name, str) or not _IDENT_RE.match(name):
        raise ValueError(f"invalid {what} '{name}': only letters, digits, underscore and hyphen allowed")
    return name


def quote_ident(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"
