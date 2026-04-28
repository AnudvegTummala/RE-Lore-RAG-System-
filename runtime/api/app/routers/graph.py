from fastapi import APIRouter, HTTPException

from app.services.neo4j_service import neo4j_service

router = APIRouter(prefix="/graph", tags=["graph"])

_SUBGRAPH_CYPHER = """
MATCH (e {id: $entity_id})
CALL apoc.path.subgraphAll(e, {maxLevel: 2, limit: 50}) YIELD nodes, relationships
RETURN nodes, relationships
"""


@router.get("/{entity_id}")
async def get_entity_subgraph(entity_id: str):
    try:
        records = await neo4j_service.run(_SUBGRAPH_CYPHER, entity_id=entity_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not records:
        raise HTTPException(status_code=404, detail="Entity not found")

    nodes: list[dict] = []
    edges: list[dict] = []
    seen_nodes: set[str] = set()
    seen_edges: set[tuple] = set()

    for record in records:
        for node in record.get("nodes", []):
            nid = str(node.get("element_id", ""))
            if nid not in seen_nodes:
                seen_nodes.add(nid)
                nodes.append({"id": nid, "labels": node.get("labels", []), **node.get("properties", {})})
        for rel in record.get("relationships", []):
            key = (str(rel.get("start_node_element_id")), rel.get("type"), str(rel.get("end_node_element_id")))
            if key not in seen_edges:
                seen_edges.add(key)
                edges.append({"source": key[0], "type": key[1], "target": key[2]})

    return {"nodes": nodes, "edges": edges}
