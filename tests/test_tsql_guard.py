import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integrations" / "mcp" / "azuresql"))
from tsql_guard import has_multiple_statements, is_read_only, validate_identifier  # noqa: E402


class TsqlGuard(unittest.TestCase):
    def test_plain_reads_ok(self):
        self.assertTrue(is_read_only("SELECT TOP 10 * FROM dbo.customers"))
        self.assertTrue(is_read_only("-- c\nWITH a AS (SELECT 1 AS x) SELECT x FROM a;"))

    def test_select_into_rejected(self):
        self.assertFalse(is_read_only("SELECT * INTO dbo.copy FROM dbo.customers"))

    def test_cte_with_dml_rejected(self):
        self.assertFalse(is_read_only("WITH a AS (SELECT 1 AS x) DELETE FROM dbo.t"))

    def test_exec_and_writes_rejected(self):
        for s in ("EXEC sp_who", "INSERT INTO t VALUES (1)", "UPDATE t SET a=1", "MERGE t USING s ON 1=1", "", "  "):
            self.assertFalse(is_read_only(s), s)

    def test_stacked_rejected(self):
        self.assertFalse(is_read_only("SELECT 1; SELECT 2"))
        self.assertTrue(has_multiple_statements("SELECT 1; SELECT 2"))

    def test_keywords_in_strings_and_brackets_ok(self):
        self.assertTrue(is_read_only("SELECT 'delete into x' AS note, [update] FROM dbo.t"))
        self.assertFalse(has_multiple_statements("SELECT 'a;b' AS x"))

    def test_identifier_validation(self):
        self.assertEqual(validate_identifier("dbo", "schema"), "dbo")
        for bad in ("a.b", "x; y", "", "[dbo]", "a b"):
            with self.assertRaises(ValueError):
                validate_identifier(bad, "schema")


if __name__ == "__main__":
    unittest.main()
