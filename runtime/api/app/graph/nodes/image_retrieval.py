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
        graph_results = state.get("graph_results", [])

        # Entity_id prefix encodes entity type (e.g. "character-leon-s-kennedy",
        # "enemy-jill-valentine", "game-resident-evil-4-2005"). Use this to
        # separate visual entities (character/enemy) from non-visual ones
        # (game/location/weapon/virus) without an extra query.
        _VISUAL_PREFIXES = ("character-", "enemy-", "organization-")

        def _is_visual(eid: str) -> bool:
            return any(eid.startswith(p) for p in _VISUAL_PREFIXES)

        # Collect visual entity_ids from graph subgraph nodes — graph_retrieval
        # returns the matched entity plus 1-hop neighbours (games, locations, etc).
        # Filter to visual prefixes only so game cover art can't enter the filter.
        graph_visual_ids: set[str] = set()
        for rec in graph_results:
            for node in rec.get("nodes", []):
                try:
                    eid = dict(node).get("id", "")
                    if eid and _is_visual(eid):
                        graph_visual_ids.add(eid)
                except Exception:
                    pass

        # Also collect visual entity_ids from text_results as a supplement.
        text_visual_ids: set[str] = {
            r.get("entity_id") for r in text_results
            if r.get("entity_id") and _is_visual(r.get("entity_id", ""))
        }

        # Priority: graph visual ids → text visual ids → all text ids (last resort)
        entity_ids = list(graph_visual_ids | text_visual_ids) \
            or list({r.get("entity_id") for r in text_results if r.get("entity_id")})

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

        logger.info(
            "image_retrieval: %d images returned (filtered=%s)",
            len(results), bool(entity_filter),
        )
        return {**state, "image_results": results}
    except Exception:
        logger.exception("image_retrieval failed")
        return {**state, "image_results": []}
