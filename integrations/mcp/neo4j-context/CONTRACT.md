# `db-kit-context` MCP contract

Status: **proposed** — to be confirmed against the actual Neo4j schema by the team building the real server. DB-Kit develops against `mock_server/` implementing this same contract until the real server is ready.

## Scope

Read access to the discovery-side knowledge graph. Write access limited to DB-Kit-authored annotations — DB-Kit never mutates canonical nodes or properties, so a refresh of the canonical graph can never clobber DB-Kit's contributions.

## Proposed graph shape

**Node labels:** `SourceSystem`, `Dataset`, `Pipeline`, `Transformation`, `BusinessRule`.
Column/schema detail is assumed to live as a property bag on `Dataset` unless the real graph models columns as their own nodes — confirm with `list_schema`.

**Relationships:** `PRODUCES` (SourceSystem→Dataset, Transformation→Dataset), `READS` / `WRITES` (Pipeline→Dataset), `EXECUTES` (Pipeline→Transformation), `DEPENDS_ON` (Dataset→Dataset), `APPLIES_TO` (BusinessRule→Dataset|Transformation).

**Annotation shape** (DB-Kit writes, never the team's canonical data):

```
(:DbKitAnnotation {
  run_id: string,
  status: "verified" | "inferred" | "unknown" | "blocked",
  note: string,
  created_by: "db-kit",
  created_at: datetime
}) -[:ANNOTATES]-> (canonical node)
```

## Tools

### `list_schema` (read)
Lists node labels and relationship types currently present in the graph, so DB-Kit never assumes a shape it hasn't confirmed.

- **Input:** `{}`
- **Output:** `{ "labels": string[], "relationship_types": string[] }`

### `get_entity` (read)
Fetches one node by id with its direct relationships.

- **Input:** `{ "id": string }`
- **Output:** `{ "id": string, "label": string, "properties": object, "relationships": [{ "type": string, "direction": "in"|"out", "target_id": string }] }`

### `query_context` (read)
Returns nodes matching a label and optional filters.

- **Input:** `{ "label": string, "filters"?: object, "limit"?: number }`
- **Output:** `{ "results": [{ "id": string, "properties": object }], "truncated": boolean }`

### `get_lineage` (read)
Traverses dependency/execution relationships from a given node.

- **Input:** `{ "id": string, "direction": "upstream"|"downstream", "depth"?: number }`
- **Output:** `{ "root_id": string, "nodes": [{ "id": string, "label": string }], "edges": [{ "type": string, "from_id": string, "to_id": string }] }`

### `annotate_entity` (write)
Creates a `DbKitAnnotation` node linked to an existing canonical node. Never modifies the canonical node itself.

- **Input:** `{ "target_id": string, "run_id": string, "status": "verified"|"inferred"|"unknown"|"blocked", "note": string }`
- **Output:** `{ "annotation_id": string }`

## Error behavior

Any tool call against an `id` that doesn't exist, or a write attempted outside `annotate_entity`, must return an explicit error — never a silent no-op. DB-Kit's discovery agents rely on this to distinguish "confirmed absent" from "query failed."
