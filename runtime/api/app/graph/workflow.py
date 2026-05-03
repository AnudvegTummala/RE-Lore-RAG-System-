from langgraph.graph import StateGraph, START, END

from app.graph.state import GraphState
from app.graph.nodes.classify import classify_query
from app.graph.nodes.graph_retrieval import graph_retrieval
from app.graph.nodes.vector_retrieval import vector_retrieval
from app.graph.nodes.rerank import rerank
from app.graph.nodes.image_retrieval import image_retrieval
from app.graph.nodes.assemble import assemble_evidence
from app.graph.nodes.generate import generate_answer


def _route_after_rerank(state: GraphState) -> str:
    return "image_retrieval" if state["needs_image_search"] else "assemble_evidence"


def build_graph() -> StateGraph:
    g = StateGraph(GraphState)

    g.add_node("classify_query", classify_query)
    g.add_node("graph_retrieval", graph_retrieval)
    g.add_node("vector_retrieval", vector_retrieval)
    g.add_node("rerank", rerank)
    g.add_node("image_retrieval", image_retrieval)
    g.add_node("assemble_evidence", assemble_evidence)
    g.add_node("generate_answer", generate_answer)

    # classify_query fans out to both retrievals simultaneously.
    # LangGraph waits for all incoming edges before running rerank (fan-in).
    g.add_edge(START, "classify_query")
    g.add_edge("classify_query", "graph_retrieval")
    g.add_edge("classify_query", "vector_retrieval")
    g.add_edge("graph_retrieval", "rerank")
    g.add_edge("vector_retrieval", "rerank")
    g.add_conditional_edges(
        "rerank",
        _route_after_rerank,
        {"image_retrieval": "image_retrieval", "assemble_evidence": "assemble_evidence"},
    )
    g.add_edge("image_retrieval", "assemble_evidence")
    g.add_edge("assemble_evidence", "generate_answer")
    g.add_edge("generate_answer", END)

    return g


compiled_graph = build_graph().compile()
