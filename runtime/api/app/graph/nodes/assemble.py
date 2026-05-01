import re

from app.graph.state import GraphState

# Minimum meaningful characters in parent_text after stripping whitespace and
# bracket-only tokens like "[ 12 ]". Sections that are purely reference lists
# ("Gallery [ ]", "History [ ]: [ 1 ] [ 2 ]") add no useful context for the LLM.
_MIN_BODY_CHARS = 80


def _meaningful_len(text: str) -> int:
    """Return length of text after stripping citation brackets like [ 12 ] or [ ]."""
    stripped = re.sub(r"\[\s*\d*\s*\]", "", text)
    return len(stripped.strip())


def assemble_evidence(state: GraphState) -> GraphState:
    parts: list[str] = []

    graph_results = state.get("graph_results", [])
    if graph_results:
        parts.append("## Graph Knowledge\n" + _format_graph(graph_results))

    text_results = state.get("text_results", [])
    # Deduplicate by (entity_id, section) — different chunk_ids from the same
    # section share the same parent_text, so including all of them is just noise.
    seen_sections: set[tuple[str, str]] = set()
    text_parts: list[str] = []
    for r in text_results:
        entity_id = r.get("entity_id", "")
        section = r.get("section", "")
        key = (entity_id, section)
        if key in seen_sections:
            continue
        seen_sections.add(key)

        # Use parent_text (full section) for LLM context.
        body = r.get("parent_text") or r.get("chunk_text") or r.get("text", "")
        if not body or _meaningful_len(body) < _MIN_BODY_CHARS:
            continue

        title = r.get("title", entity_id)
        text_parts.append(f"### {title} — {section}\n{body}")

    if text_parts:
        parts.append("## Lore Excerpts\n\n" + "\n\n".join(text_parts))

    image_results = state.get("image_results", [])
    if image_results:
        captions = [
            f"- {r.get('caption') or r.get('image_id', '?')} (entity: {r.get('entity_id', '?')})"
            for r in image_results
        ]
        parts.append(
            "## Concept Art Found\n"
            "The following concept art images are being displayed to the user alongside this answer:\n"
            + "\n".join(captions)
        )

    evidence = "\n\n".join(parts) if parts else "No relevant lore found."
    return {**state, "evidence": evidence}


def _format_graph(records: list[dict]) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for rec in records:
        for node in rec.get("nodes", []):
            try:
                labels = list(node.labels)
                props = dict(node)
                label = labels[0] if labels else "Entity"
                name = props.get("title") or props.get("name") or props.get("id", "?")
                key = f"{label}:{name}"
                if key not in seen:
                    seen.add(key)
                    lines.append(f"- {label}: {name}")
            except Exception:
                pass
    return "\n".join(lines) if lines else "(empty)"
