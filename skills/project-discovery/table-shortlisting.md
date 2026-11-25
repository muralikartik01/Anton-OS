# Skill: Table shortlisting

**Used by:** Discovery Agent.

**Purpose:** Narrow a workflow run's scope to a concrete, named list of tables/datasets before any profiling or rule generation starts — so later stages never operate on an unbounded "all tables" scope.

**Adapted from:** `data-product-orchestrator`'s `discovery_analysis/skills/table_shortlisting.md` (BRD-driven shortlisting). DB-Kit's version is scope-driven rather than BRD-driven: the input is the run's declared scope (explicit table names, a source-system name, or a schema pattern), not a business requirements document.

## Procedure

1. Resolve the run's requested scope (explicit table list, or a source-system/schema filter) against the knowledge graph: call `query_context` on the `db-kit-context` MCP server with `label: "Dataset"` and the relevant filter.
2. For any table the user named that isn't found in the graph, fall back to a direct `information_schema` query against the declared source connection — never assume a table exists without checking one of the two.
3. Produce a shortlist: `{ table, source: "graph"|"information_schema"|"not_found", id }` for every requested table.
4. Anything in `not_found` is a gap — surface it in the discovery report rather than silently dropping it from scope.

## Output

A shortlist array consumed by the profiling and quality-rule-generation skills. Every entry must be traceable to where it was confirmed (graph entity id, or the live schema query that found it).
