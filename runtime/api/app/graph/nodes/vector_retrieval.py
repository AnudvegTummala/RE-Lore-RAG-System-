import logging

from app.graph.state import GraphState
from app.services.qdrant_service import qdrant_service

logger = logging.getLogger(__name__)


async def vector_retrieval(state: GraphState) -> GraphState:
    try:
        results = await qdrant_service.search_text(
            query=state["query"],
            collection="lore_text",
            limit=15,
        )
        logger.info("vector_retrieval: %d candidates returned", len(results))
        return {"text_results": results}
    except Exception:
        logger.exception("vector_retrieval failed")
        return {"text_results": []}
