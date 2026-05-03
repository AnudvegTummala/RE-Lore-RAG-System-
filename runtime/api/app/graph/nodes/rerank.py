import asyncio
import logging

from sentence_transformers import CrossEncoder

from app.core.config import settings
from app.graph.state import GraphState

logger = logging.getLogger(__name__)

_TOP_K = 3

_cross_encoder = CrossEncoder(settings.reranker_model)


async def rerank(state: GraphState) -> GraphState:
    text_results = state.get("text_results", [])
    if len(text_results) <= 1:
        return state

    query = state["query"]
    passages = [
        r.get("chunk_text") or r.get("parent_text") or r.get("text", "")
        for r in text_results
    ]
    pairs = [[query, p] for p in passages]

    try:
        loop = asyncio.get_running_loop()
        scores: list[float] = await loop.run_in_executor(
            None, _cross_encoder.predict, pairs
        )
        ranked = sorted(zip(scores, text_results), key=lambda x: x[0], reverse=True)
        above_threshold = [r for score, r in ranked if score >= 0.3]
        reranked = (above_threshold or [ranked[0][1]])[:_TOP_K]
        top_score = ranked[0][0] if ranked else 0.0
        logger.info(
            "rerank: %d candidates → %d above threshold 0.3 (top score: %.2f), kept %d",
            len(text_results), len(above_threshold), top_score, len(reranked),
        )
        return {**state, "text_results": reranked}
    except Exception:
        logger.exception("rerank failed — returning text_results unchanged")
        return state
