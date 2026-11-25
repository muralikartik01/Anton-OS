# Target-platform rules — Databricks medallion pilot (landing -> Bronze -> Silver)

- Platform: a real Databricks workspace (Unity Catalog, Delta), non-production test catalog, declared in `config/integrations.yaml`. Treat any connection not declared there as out of scope.
- Catalog and schema names are **workflow inputs** (`/db-kit-migrate --landing <catalog>.<schema>`), recorded in the run record — never hardcode them in skills, rules, or generated notebooks; parameterize them.
- Use Unity Catalog three-level names (`catalog.schema.table`) everywhere. Source and target are both Databricks, so no cross-engine type mapping is needed; type changes (e.g. STRING -> DATE/DECIMAL) are explicit casts documented in the mapping.
- All SQL executes through the `db-kit-databricks` MCP server. The exact SQL text embedded in a generated notebook is the text passed to `execute_statement` — never re-render it differently.
- Only the Validation Agent calls `execute_statement`, at the start of Stage 6, after the Stage 4 blueprint approval is recorded. The Transformation Agent never executes anything.
- Generated notebooks follow `docs/reference/tiger-copilot-instructions.md` coding standards: 4-space indent, snake_case tables/columns, capitalized SQL keywords, CTEs for complex queries, no `SELECT *`.
- This pilot is intentionally narrow (one platform) per spec §1 — do not generalize generated code to other platforms speculatively.
- Source types supported as run inputs: `databricks` (landing already populated) `azuresql` (read-only via `db-kit-azuresql`) and `postgres` (Azure Database for PostgreSQL, read-only via `db-kit-postgres`), both loaded into landing by `landing_load`. JDBC credentials are referenced only through Databricks `secret(scope, key)` — never literal values in SQL, notebooks, config or chat.
