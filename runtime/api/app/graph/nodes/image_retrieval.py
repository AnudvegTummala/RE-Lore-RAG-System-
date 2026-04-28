import logging

from app.graph.state import GraphState
from app.services.clip_service_client import clip_client
from app.services.qdrant_service import qdrant_service

logger = logging.getLogger(__name__)


async def image_retrieval(state: GraphState) -> GraphState:
    try:
        vector = await clip_client.embed_text(state["query"])
        results = await qdrant_service.search_by_vector(
            vector=vector,
            collection="concept_art",
            limit=3,
        )
        return {**state, "image_results": results}
    except Exception:
        logger.exception("image_retrieval failed")
        return {**state, "image_results": []}
