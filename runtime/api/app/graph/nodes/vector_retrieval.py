import logging

from app.graph.state import GraphState
from app.services.qdrant_service import qdrant_service

logger = logging.getLogger(__name__)


async def vector_retrieval(state: GraphState) -> GraphState:
    try:
        results = await qdrant_service.search_text(
            query=state["query"],
            collection="lore_text",
            limit=5,
        )
        return {**state, "text_results": results}
    except Exception:
        logger.exception("vector_retrieval failed")
        return {**state, "text_results": []}
