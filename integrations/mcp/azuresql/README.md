# db-kit-azuresql connector

Read-only MCP server over `pymssql`. Contract: `CONTRACT.md`.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example my.env   # edit, `source my.env`, then launch `claude` from that shell
```
Registered in the repo-root `.mcp.json`. Tests: `python3 -m unittest discover -s tests -v` from the repo root. The Azure SQL firewall must allow your client IP.
