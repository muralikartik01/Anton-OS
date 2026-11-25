# Data-engineering / SQL standards

- Identifiers: `lower_snake_case` for tables, columns, and files.
- Every generated transformation must be idempotent — safe to re-run without duplicating or corrupting data.
- Every generated table/view must have an explicit, documented schema (types, nullability, keys) — no implicit/inferred-only schemas in generated artifacts.
- Incremental load logic must state its watermark/key strategy explicitly; do not assume full-refresh unless the source has no reliable incremental key.
- Generated SQL/code must target the platform declared for that layer in `project.yaml` (Databricks / Unity Catalog three-level names for this pilot; catalog and schema come from the run's inputs) — do not generate platform-agnostic pseudocode as a final artifact.
