import logging

from app.graph.state import GraphState
from app.services.neo4j_service import neo4j_service

logger = logging.getLogger(__name__)

_CYPHER = """
MATCH (e)
WHERE any(hint IN $hints WHERE toLower(coalesce(e.title, '')) CONTAINS toLower(hint))
WITH e LIMIT 5
CALL apoc.path.subgraphAll(e, {maxLevel: 2, limit: 50}) YIELD nodes, relationships
RETURN nodes, relationships
"""


async def graph_retrieval(state: GraphState) -> GraphState:
    hints = state.get("entity_hints", [])
    if not hints:
        logger.info("graph_retrieval: no hints, skipped")
        return {**state, "graph_results": []}

    try:
        records = await neo4j_service.run(_CYPHER, hints=hints)
        logger.info("graph_retrieval: %d hints → %d records", len(hints), len(records))
        return {**state, "graph_results": records}
    except Exception:
        logger.exception("graph_retrieval failed")
        return {**state, "graph_results": []}
