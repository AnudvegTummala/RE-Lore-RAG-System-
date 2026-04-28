from app.graph.state import GraphState


def assemble_evidence(state: GraphState) -> GraphState:
    parts: list[str] = []

    graph_results = state.get("graph_results", [])
    if graph_results:
        parts.append("## Graph Knowledge\n" + _format_graph(graph_results))

    text_results = state.get("text_results", [])
    seen_chunks: set[str] = set()
    text_parts: list[str] = []
    for r in text_results:
        chunk_id = r.get("chunk_id", r.get("text", "")[:64])
        if chunk_id not in seen_chunks:
            seen_chunks.add(chunk_id)
            text_parts.append(f"- [{r.get('section', 'Lore')}] {r.get('text', '')}")
    if text_parts:
        parts.append("## Lore Excerpts\n" + "\n".join(text_parts))

    evidence = "\n\n".join(parts) if parts else "No relevant lore found."
    return {**state, "evidence": evidence}


def _format_graph(records: list[dict]) -> str:
    lines: list[str] = []
    for rec in records:
        for node in rec.get("nodes", []):
            props = node.get("properties", {})
            lines.append(f"- {node.get('labels', ['?'])[0]}: {props.get('name', '?')}")
    return "\n".join(lines) if lines else "(empty)"
