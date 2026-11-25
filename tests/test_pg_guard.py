import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integrations" / "mcp" / "postgres"))
from pg_guard import has_multiple_statements, is_read_only, validate_identifier  # noqa: E402


class PgGuard(unittest.TestCase):
    def test_plain_reads_ok(self):
        self.assertTrue(is_read_only("SELECT * FROM public.customers LIMIT 10"))
        self.assertTrue(is_read_only("-- c\nWITH a AS (SELECT 1 AS x) SELECT x FROM a;"))
        self.assertTrue(is_read_only("SELECT name FROM t WHERE name LIKE '%drop%'"))
        self.assertTrue(is_read_only('SELECT "delete" FROM t'))

    def test_select_into_and_cte_dml_rejected(self):
        self.assertFalse(is_read_only("SELECT * INTO copy FROM public.customers"))
        self.assertFalse(is_read_only("WITH d AS (DELETE FROM t RETURNING *) SELECT * FROM d"))

    def test_writes_and_commands_rejected(self):
        for s in ("INSERT INTO t VALUES (1)", "UPDATE t SET a=1", "COPY t TO '/tmp/x'", "CALL p()", "DO $$ BEGIN END $$",
                  "SET search_path = x", "", "  "):
            self.assertFalse(is_read_only(s), s)

    def test_side_effect_functions_rejected(self):
        for s in ("SELECT set_config('a','b',false)", "SELECT nextval('s')", "SELECT pg_read_file('/etc/passwd')",
                  "SELECT lo_import('/x')", "SELECT * FROM dblink('x','y') AS t(a int)"):
            self.assertFalse(is_read_only(s), s)

    def test_dollar_quoted_text_ignored(self):
        self.assertTrue(is_read_only("SELECT $q$ delete insert $q$ AS note"))

    def test_stacked_rejected(self):
        self.assertFalse(is_read_only("SELECT 1; SELECT 2"))
        self.assertTrue(has_multiple_statements("SELECT 1; SELECT 2"))
        self.assertFalse(has_multiple_statements("SELECT 1;"))

    def test_identifier_validation(self):
        self.assertEqual(validate_identifier("raw_dump", "schema"), "raw_dump")
        with self.assertRaises(ValueError):
            validate_identifier("a;b", "schema")


if __name__ == "__main__":
    unittest.main()
