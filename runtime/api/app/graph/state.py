from typing import TypedDict


class GraphState(TypedDict):
    query: str
    entity_hints: list[str]
    needs_image_search: bool
    graph_results: list[dict]
    text_results: list[dict]
    image_results: list[dict]
    evidence: str
    answer: str
    retrieval_adequate: bool
