# Medallion architecture rules

- **Bronze:** raw, append-only, minimally transformed copy of source data. Preserve source schema; add ingestion metadata (load timestamp, source system, batch/run id) only — no business logic.
- **Silver:** cleaned, conformed, deduplicated, with business rules applied and explicitly cited in the Migration Mapping. Schema may diverge from source to match target conventions.
- **Gold:** out of scope for Phase 1 (spec §1) — do not generate Gold artifacts or mappings.
- Every Bronze→Silver transformation must be traceable to a Migration Mapping entry; no undocumented transformation logic.
- A dataset's Layer assignment is a DB-Kit decision recorded in the Migration Mapping (repo files), not written to the Neo4j knowledge graph.
