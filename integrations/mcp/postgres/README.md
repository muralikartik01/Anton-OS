Read-only MCP server over `psycopg` for Azure Database for PostgreSQL. Contract: `CONTRACT.md`.

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```
Credentials: environment variables only, see `.env.example`. Registered in the repo-root `.mcp.json` as `db-kit-postgres`.
