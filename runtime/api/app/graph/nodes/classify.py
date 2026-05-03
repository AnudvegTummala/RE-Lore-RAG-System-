import re

from app.graph.state import GraphState

_VISUAL_KEYWORDS = re.compile(
    r"\b(look(s)? like|concept art|appearance|design|portrait|image|picture|photo|"
    r"visual|render|model|outfit|costume|face|hair|eye)\b",
    re.IGNORECASE,
)

# Title-cased names: "Albert Wesker", "Leon Kennedy"
_TITLE_CASE = re.compile(r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b")
# All-caps acronyms: BSAA, STARS, BOW (2+ chars to avoid single-letter noise)
_ALL_CAPS = re.compile(r"\b[A-Z]{2,}\b")
# Dotted abbreviations: S.T.A.R.S., B.O.W.
_DOTTED = re.compile(r"\b(?:[A-Z]\.){2,}")
# Hyphenated type names: T-Virus, G-Virus, T-Abyss, T-Veronica
_HYPHENATED = re.compile(r"\b[A-Z]-[A-Za-z][A-Za-z]+\b")

# Known lowercase aliases that the patterns above would miss entirely
_KNOWN_ALIASES: set[str] = {
    "bsaa", "stars", "s.t.a.r.s", "bow", "umbrella", "tricell",
    "t-virus", "g-virus", "t-abyss", "t-veronica", "las plagas",
}


def _extract_hints(query: str) -> list[str]:
    hits: list[str] = []
    hits += _TITLE_CASE.findall(query)
    hits += _ALL_CAPS.findall(query)
    hits += [m.rstrip(".") for m in _DOTTED.findall(query)]
    hits += _HYPHENATED.findall(query)

    # Lowercase fallback: if nothing found, check against known aliases
    if not hits:
        q_lower = query.lower()
        hits += [alias for alias in _KNOWN_ALIASES if alias in q_lower]

    return list(dict.fromkeys(hits))


def classify_query(state: GraphState) -> GraphState:
    query = state["query"]
    return {
        **state,
        "entity_hints": _extract_hints(query),
        "needs_image_search": bool(_VISUAL_KEYWORDS.search(query)),
    }
