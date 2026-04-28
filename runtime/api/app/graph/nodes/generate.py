import logging

from app.graph.state import GraphState
from app.services.llm import get_llm
from app.services.prompt_builder import build_prompt

logger = logging.getLogger(__name__)


async def generate_answer(state: GraphState) -> GraphState:
    llm = get_llm()
    prompt = build_prompt(query=state["query"], evidence=state["evidence"])

    try:
        response = await llm.ainvoke(prompt)
        answer = response.content
        retrieval_adequate = len(state.get("evidence", "")) > 50
        return {**state, "answer": answer, "retrieval_adequate": retrieval_adequate}
    except Exception:
        logger.exception("generate_answer failed")
        return {
            **state,
            "answer": "I encountered an error generating a response. Please try again.",
            "retrieval_adequate": False,
        }
