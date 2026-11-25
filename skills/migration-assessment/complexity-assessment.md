# Skill: Complexity assessment

**Used by:** Migration Architect Agent.

**Purpose:** Stage 2 of `legacy_to_bronze_silver_migration` — turn discovery evidence into an honest assessment of how hard and how risky the migration is, and in what order to do it, before any blueprint is drafted.

**Adapted from:** none — written fresh per spec §11 Stage 2. There is no close equivalent in `data-product-orchestrator` or the onboarded Tiger skills.

## Procedure

Working only from the discovery profile, table shortlist and knowledge-graph context (cite each finding; never assert an unprofiled fact):

1. **Complexity per table.** Rate low/medium/high using evidence: column count, type-cast count (STRING landing columns with a comment naming a cast), cast-failure rate from profiling, number of business rules touching it, whether it needs deduplication.
2. **Dependency risk.** From PK/FK relationships, list which tables must load before others (parents before children) and any orphaned or circular references found.
3. **Ambiguous logic.** List every rule, enum, reconciliation or column meaning that is unclear or undocumented. Each becomes an open question for the blueprint — do not resolve it by assumption.
4. **Volume and incremental considerations.** Row counts, growth hints (e.g. `_landed_at` spread), and the load strategy implied: merge key present, PK only, or full reload.
5. **Platform compatibility.** Databricks/Unity Catalog checks: three-level names resolvable, catalog/schema access via `list_tables`/`describe_table`, types castable to Delta types, anything needing features outside Phase 1 (Gold, production writes).
6. **Migration-order recommendation.** Ordered list (dimensions/parents first, facts/children last), each step with a one-line reason.

## Output

`assessment.md` under `artifacts/discovery/<project-id>/<run-id>/` (or the workflow's equivalent path):

| Table | Complexity | Dependencies | Risk | Evidence | Open question |
|---|---|---|---|---|---|

followed by the ordered migration-order list. Every open question also goes to `risks.md`. Stage 3 may not start with an unstated assumption standing in for an open question.
