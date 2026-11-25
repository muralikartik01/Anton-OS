# Skill: Repository analysis

**Used by:** Discovery Agent.

**Purpose:** Inventory the legacy pipeline/transformation code actually sitting in the repository — the part of the Project Context Model that isn't captured in the Neo4j knowledge graph (which only models datasets/pipelines as entities, not their implementation).

## Procedure

1. Walk the repository paths declared in `config/project.yaml`.
2. Identify files that implement a transformation (SQL scripts, Python/Spark jobs, scheduler configs, dbt models, etc.) rather than just scanning everything indiscriminately.
3. For each one found, record: file path, inferred language/platform, which dataset(s) it reads/writes (by name, to be matched against the knowledge graph's `Dataset` nodes), and any scheduling/trigger info visible in the file itself.
4. Cross-reference against `db-kit-context` MCP: if a file implements a pipeline the graph already models, link them by id; if not, flag it as a gap (pipeline exists in the repo but isn't represented in the graph yet).
5. Respect `policy.context_budget` (soft warning) — record actual files/bytes read in the discovery report.

## Output

A code inventory: `{ file_path, language, reads: [dataset_name], writes: [dataset_name], graph_entity_id: string|null }[]`, feeding the discovery report and, for unmatched pipelines, an `annotate_entity`-worthy gap.
