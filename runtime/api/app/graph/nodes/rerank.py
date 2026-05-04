import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from sentence_transformers import CrossEncoder

from app.core.config import settings
from app.graph.state import GraphState

logger = logging.getLogger(__name__)

_TOP_K = 3

# Dedicated single-thread executor for cross-encoder inference.
# Using the default shared ThreadPoolExecutor (None) causes a deadlock on
# CPU Docker: PyTorch/OpenMP spawns internal threads that compete with the
# asyncio pool for OS thread slots, starving the executor submit call.
# A dedicated max_workers=1 executor gives the cross-encoder a guaranteed
# slot that is never contended by other asyncio tasks.
# OMP_NUM_THREADS=1 and TOKENIZERS_PARALLELISM=false must also be set in
# the container environment (see docker-compose.yml) to prevent OpenMP from
# spawning threads inside this worker — torch.set_num_threads(1) alone does
# not suppress the OpenMP thread pool.
_RERANKER_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="reranker")
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
            _RERANKER_EXECUTOR, _cross_encoder.predict, pairs
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
