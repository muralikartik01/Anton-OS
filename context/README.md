# Context directory

Per `docs/superpowers/specs/2026-11-23-db-kit-v1-gap-resolutions-design.md` §1, the discovery-side knowledge graph (source systems, datasets, schemas, pipelines, transformations, dependencies) is **not stored here**. It lives in the team's Neo4j graph, accessed via the `db-kit-context` MCP server (see `integrations/mcp/neo4j-context/`).

`context/graph/`, `context/lineage/`, and `context/metadata/` are kept as empty placeholders from the original spec structure but are not used in Phase 1 — do not populate them; that data is externalized to Neo4j.

This directory holds only what DB-Kit itself owns:

- `decisions/` — approved assumptions, migration preferences, architecture conventions, with date/scope/status/rationale (spec §6.2).
- `project-profile/` — onboarding output: project profile, source/target technology profile, repository inventory (spec §4.3).

Run-specific state (Migration Mapping, Decision, Validation Result, Workflow Run) lives in `observability/run-records/` and `artifacts/`, not here.
