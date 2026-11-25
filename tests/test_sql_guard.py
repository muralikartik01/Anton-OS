import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integrations" / "mcp" / "databricks-sql"))
from sql_guard import has_multiple_statements, is_read_only, quote_ident, validate_identifier  # noqa: E402


class SqlGuard(unittest.TestCase):
    def test_select_and_with_ok(self):
        self.assertTrue(is_read_only("SELECT 1"))
        self.assertTrue(is_read_only("  -- c\n WITH a AS (SELECT 1) SELECT * FROM a;"))
        self.assertTrue(is_read_only("DESCRIBE TABLE x.y.z"))

    def test_writes_rejected(self):
        for s in ("INSERT INTO t VALUES (1)", "CREATE TABLE t AS SELECT 1", "MERGE INTO t USING s ON 1=1", "", "   "):
            self.assertFalse(is_read_only(s), s)

    def test_stacked_statements_rejected(self):
        self.assertFalse(is_read_only("SELECT 1; INSERT INTO t VALUES (1)"))
        self.assertTrue(has_multiple_statements("SELECT 1; SELECT 2"))

    def test_semicolon_in_string_ok(self):
        self.assertFalse(has_multiple_statements("SELECT 'a;b' AS x"))

    def test_trailing_semicolon_and_comment_ok(self):
        self.assertFalse(has_multiple_statements("SELECT 1; -- done"))

    def test_identifier_validation(self):
        self.assertEqual(validate_identifier("retail_dev", "catalog"), "retail_dev")
        for bad in ("a.b", "x; y", "", "a b", "`x`"):
            with self.assertRaises(ValueError):
                validate_identifier(bad, "catalog")

    def test_quote_ident(self):
        self.assertEqual(quote_ident("a`b"), "`a``b`")


if __name__ == "__main__":
    unittest.main()
