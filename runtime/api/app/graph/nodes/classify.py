import re

from app.graph.state import GraphState

_VISUAL_KEYWORDS = re.compile(
    r"\b(look(s)? like|concept art|appearance|design|portrait|image|picture|photo|"
    r"visual|render|model|outfit|costume|face|hair|eye)\b",
    re.IGNORECASE,
)

_ENTITY_PATTERN = re.compile(r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b")


def classify_query(state: GraphState) -> GraphState:
    query = state["query"]

    entity_hints = _ENTITY_PATTERN.findall(query)
    needs_image_search = bool(_VISUAL_KEYWORDS.search(query))

    return {
        **state,
        "entity_hints": list(dict.fromkeys(entity_hints)),
        "needs_image_search": needs_image_search,
    }
