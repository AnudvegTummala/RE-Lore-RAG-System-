import asyncio
import logging

import torch
from sentence_transformers import CrossEncoder

from app.core.config import settings
from app.graph.state import GraphState

logger = logging.getLogger(__name__)

_TOP_K = 3

# Prevent PyTorch from spawning excessive CPU threads inside the container,
# which causes deadlocks when predict() runs in the asyncio thread pool.
torch.set_num_threads(1)

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
        reranked = [r for _, r in ranked[:_TOP_K]]
        return {**state, "text_results": reranked}
    except Exception:
        logger.exception("rerank failed — returning text_results unchanged")
        return state
