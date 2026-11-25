"""Mock db-kit-context MCP server.

Implements the tool contract in integrations/mcp/neo4j-context/CONTRACT.md
against fixture data, so DB-Kit's discovery/validation agents can be built
and demoed against something before the real Neo4j MCP server (built by
the knowledge-graph team) is ready.

Canonical graph data (fixtures.json) and DB-Kit's own annotations
(annotations.json) are kept in separate files on purpose: this mirrors the
real server's contract, where DB-Kit writes DbKitAnnotation nodes linked to
canonical nodes but never touches the canonical nodes/properties themselves.

Run with: python3 server.py
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer

FIXTURES_PATH = Path(__file__).parent / "fixtures.json"
ANNOTATIONS_PATH = Path(__file__).parent / "annotations.json"

EDGE_TYPES_BY_DIRECTION = {
    "downstream": ["DEPENDS_ON"],
    "upstream": ["DEPENDS_ON"],
}


def _load_graph() -> dict[str, Any]:
    return json.loads(FIXTURES_PATH.read_text())


def _load_annotations() -> dict[str, Any]:
    return json.loads(ANNOTATIONS_PATH.read_text())


def _save_annotations(data: dict[str, Any]) -> None:
    ANNOTATIONS_PATH.write_text(json.dumps(data, indent=2) + "\n")


def _find_node(graph: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    return next((n for n in graph["nodes"] if n["id"] == node_id), None)


server = MCPServer(
    name="db-kit-context",
    description="Mock Neo4j knowledge-graph MCP server for DB-Kit Phase 1.",
)


@server.tool()
def list_schema() -> dict[str, Any]:
    """List node labels and relationship types currently present in the graph."""
    graph = _load_graph()
    labels = sorted({n["label"] for n in graph["nodes"]})
    relationship_types = sorted({e["type"] for e in graph["edges"]})
    return {"labels": labels, "relationship_types": relationship_types}


@server.tool()
def get_entity(id: str) -> dict[str, Any]:
    """Fetch one node by id with its direct relationships, in either direction."""
    graph = _load_graph()
    node = _find_node(graph, id)
    if node is None:
        raise ValueError(f"No entity with id '{id}' exists in the knowledge graph.")

    relationships = []
    for edge in graph["edges"]:
        if edge["from_id"] == id:
            relationships.append({"type": edge["type"], "direction": "out", "target_id": edge["to_id"]})
        elif edge["to_id"] == id:
            relationships.append({"type": edge["type"], "direction": "in", "target_id": edge["from_id"]})

    return {"id": node["id"], "label": node["label"], "properties": node["properties"], "relationships": relationships}


@server.tool()
def query_context(label: str, filters: dict[str, Any] | None = None, limit: int | None = None) -> dict[str, Any]:
    """Return nodes matching a label and optional property filters."""
    graph = _load_graph()
    filters = filters or {}
    matches = [
        n for n in graph["nodes"]
        if n["label"] == label and all(n["properties"].get(k) == v for k, v in filters.items())
    ]
    truncated = limit is not None and len(matches) > limit
    if limit is not None:
        matches = matches[:limit]
    return {
        "results": [{"id": n["id"], "properties": n["properties"]} for n in matches],
        "truncated": truncated,
    }


@server.tool()
def get_lineage(id: str, direction: Literal["upstream", "downstream"], depth: int = 1) -> dict[str, Any]:
    """Traverse DEPENDS_ON/READS/WRITES/EXECUTES/PRODUCES relationships from a node."""
    graph = _load_graph()
    if _find_node(graph, id) is None:
        raise ValueError(f"No entity with id '{id}' exists in the knowledge graph.")

    traversal_types = {"DEPENDS_ON", "READS", "WRITES", "EXECUTES", "PRODUCES"}
    visited_nodes: dict[str, str] = {}
    visited_edges: list[dict[str, str]] = []
    frontier = {id}

    for _ in range(max(depth, 1)):
        next_frontier: set[str] = set()
        for edge in graph["edges"]:
            if edge["type"] not in traversal_types:
                continue
            # "downstream" follows edges forward (from -> to); "upstream" follows them backward.
            if direction == "downstream" and edge["from_id"] in frontier:
                next_frontier.add(edge["to_id"])
                visited_edges.append(edge)
            elif direction == "upstream" and edge["to_id"] in frontier:
                next_frontier.add(edge["from_id"])
                visited_edges.append(edge)
        if not next_frontier:
            break
        for nid in next_frontier:
            node = _find_node(graph, nid)
            if node:
                visited_nodes[nid] = node["label"]
        frontier = next_frontier

    return {
        "root_id": id,
        "nodes": [{"id": nid, "label": label} for nid, label in visited_nodes.items()],
        "edges": [{"type": e["type"], "from_id": e["from_id"], "to_id": e["to_id"]} for e in visited_edges],
    }


@server.tool()
def annotate_entity(target_id: str, run_id: str, status: Literal["verified", "inferred", "unknown", "blocked"], note: str) -> dict[str, str]:
    """Create a DbKitAnnotation linked to an existing canonical node. Never modifies the canonical node."""
    graph = _load_graph()
    if _find_node(graph, target_id) is None:
        raise ValueError(f"Cannot annotate '{target_id}': no such entity in the knowledge graph.")

    annotations = _load_annotations()
    annotation_id = f"annotation-{uuid.uuid4().hex[:12]}"
    annotations["annotations"].append({
        "annotation_id": annotation_id,
        "target_id": target_id,
        "run_id": run_id,
        "status": status,
        "note": note,
        "created_by": "db-kit",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    _save_annotations(annotations)
    return {"annotation_id": annotation_id}


if __name__ == "__main__":
    server.run("stdio")
