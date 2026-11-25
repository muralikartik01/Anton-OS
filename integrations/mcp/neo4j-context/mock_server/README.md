# db-kit-context mock server

Implements `../CONTRACT.md` against `fixtures.json`, so DB-Kit can be developed/demoed against the knowledge graph before the real Neo4j MCP server exists.

## Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
. .venv/bin/activate
python3 server.py
```

Runs over stdio. Register it in Claude Code as a project MCP server pointing at this command, or run the tool functions directly for a smoke test:

```bash
python3 -c "import server as s; print(s.list_schema())"
```

## Data

- `fixtures.json` — canonical graph (a small legacy-orders sample: 1 source system, 4 datasets, 1 pipeline, 1 transformation, 1 business rule). Never modified by `annotate_entity`.
- `annotations.json` — DB-Kit-authored `DbKitAnnotation` records, appended by `annotate_entity`, kept separate from canonical data by design.

Swap `fixtures.json` for a different sample, or point the real server's connection details here once the knowledge-graph team's implementation is ready — the tool contract stays the same either way.
