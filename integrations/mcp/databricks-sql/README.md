# db-kit-databricks connector

Real MCP server over `databricks-sql-connector`. Contract: `CONTRACT.md`.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example my.env      # edit with your values; my.env is not tracked
source my.env               # then launch `claude` from the same shell
```

The server is registered in the repo-root `.mcp.json`; Claude Code starts it on demand and it inherits the exported `DB_KIT_DBX_*` variables. Approve the project MCP server when Claude Code prompts.

## Test

`python3 -m unittest discover -s tests -v` from the repo root (pure SQL-guard and hook tests; no workspace needed).
