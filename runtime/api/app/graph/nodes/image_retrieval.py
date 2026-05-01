import logging

from qdrant_client.models import Filter, FieldCondition, MatchValue

from app.graph.state import GraphState
from app.services.clip_service_client import clip_client
from app.services.qdrant_service import qdrant_service

logger = logging.getLogger(__name__)


async def image_retrieval(state: GraphState) -> GraphState:
    try:
        vector = await clip_client.embed_text(state["query"])

        # Build an entity filter from the text_results already retrieved by
        # vector_retrieval. Those results correctly identify which entities match
        # the query; filtering concept_art to only those entities prevents CLIP
        # from returning visually similar images of the WRONG character.
        text_results = state.get("text_results", [])
        entity_ids = list({r.get("entity_id") for r in text_results if r.get("entity_id")})

        entity_filter: Filter | None = None
        if entity_ids:
            entity_filter = Filter(
                should=[
                    FieldCondition(key="entity_id", match=MatchValue(value=eid))
                    for eid in entity_ids
                ]
            )

        results = await qdrant_service.search_by_vector(
            vector=vector,
            collection="concept_art",
            limit=5,
            query_filter=entity_filter,
        )

        # Fall back to unfiltered search if no images found for the specific entities.
        if not results:
            results = await qdrant_service.search_by_vector(
                vector=vector,
                collection="concept_art",
                limit=3,
            )

        return {**state, "image_results": results}
    except Exception:
        logger.exception("image_retrieval failed")
        return {**state, "image_results": []}
