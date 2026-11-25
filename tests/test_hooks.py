"""Run: python3 -m unittest discover -s tests -v"""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORDS = ROOT / "observability" / "run-records"
DROP = "DR" + "OP TABLE a.b.c"  # built piecewise so this file never trips the destructive-SQL hook itself
TRUNC = "TRUNC" + "ATE TABLE x"


def run_hook(rel, payload, env=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith("DB_KIT_")}
    e.update(env or {})
    r = subprocess.run([sys.executable, str(ROOT / rel)], input=json.dumps(payload), text=True, capture_output=True, env=e)
    return r.returncode, r.stderr


class DestructiveSql(unittest.TestCase):
    H = "hooks/pre-execution/block_destructive_sql.py"

    def test_blocks_mcp_sql_param(self):
        rc, _ = run_hook(self.H, {"tool_name": "mcp__db-kit-databricks__execute_statement", "tool_input": {"sql": DROP, "run_id": "x"}})
        self.assertEqual(rc, 2)

    def test_allows_create_as_select(self):
        rc, _ = run_hook(self.H, {"tool_name": "mcp__db-kit-databricks__execute_statement", "tool_input": {"sql": "CREATE TABLE a.b.c AS SELECT 1"}})
        self.assertEqual(rc, 0)

    def test_still_blocks_bash(self):
        rc, _ = run_hook(self.H, {"tool_name": "Bash", "tool_input": {"command": TRUNC}})
        self.assertEqual(rc, 2)

    def test_human_override(self):
        rc, _ = run_hook(self.H, {"tool_name": "Bash", "tool_input": {"command": DROP}}, {"DB_KIT_DESTRUCTIVE_APPROVED": "1"})
        self.assertEqual(rc, 0)


class BlueprintApproval(unittest.TestCase):
    H = "hooks/validation/require_blueprint_approval.py"
    TOOL = "mcp__db-kit-databricks__execute_statement"

    def setUp(self):
        RECORDS.mkdir(parents=True, exist_ok=True)
        self.files = []

    def tearDown(self):
        for f in self.files:
            f.unlink(missing_ok=True)

    def record(self, run_id, body):
        p = RECORDS / f"{run_id}.yaml"
        p.write_text(body)
        self.files.append(p)

    def test_other_tools_pass(self):
        self.assertEqual(run_hook(self.H, {"tool_name": "mcp__db-kit-databricks__list_tables", "tool_input": {}})[0], 0)

    def test_blocks_missing_record(self):
        self.assertEqual(run_hook(self.H, {"tool_name": self.TOOL, "tool_input": {"run_id": "nope-123"}})[0], 2)

    def test_blocks_without_approval(self):
        self.record("t-noappr", "run_id: t-noappr\napprovals: []\n")
        self.assertEqual(run_hook(self.H, {"tool_name": self.TOOL, "tool_input": {"run_id": "t-noappr"}})[0], 2)

    def test_allows_with_approval(self):
        self.record("t-appr", "run_id: t-appr\napprovals:\n  - stage: migration_blueprint\n    approved_by: me\n")
        self.assertEqual(run_hook(self.H, {"tool_name": self.TOOL, "tool_input": {"run_id": "t-appr"}})[0], 0)

    def test_rejects_path_traversal_run_id(self):
        self.assertEqual(run_hook(self.H, {"tool_name": self.TOOL, "tool_input": {"run_id": "../../etc/x"}})[0], 2)

    def test_rejects_empty_run_id(self):
        self.assertEqual(run_hook(self.H, {"tool_name": self.TOOL, "tool_input": {"sql": "x"}})[0], 2)


if __name__ == "__main__":
    unittest.main()
