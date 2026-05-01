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
        chunk_id = r.get("chunk_id", "")
        if chunk_id in seen_chunks:
            continue
        seen_chunks.add(chunk_id)
        # Ingestor stores parent_text (full section) for LLM context; fall back to
        # chunk_text (prefixed child) then legacy 'text' field.
        body = r.get("parent_text") or r.get("chunk_text") or r.get("text", "")
        if body:
            text_parts.append(f"- [{r.get('section', 'Lore')}] {body}")
    if text_parts:
        parts.append("## Lore Excerpts\n" + "\n".join(text_parts))

    evidence = "\n\n".join(parts) if parts else "No relevant lore found."
    return {**state, "evidence": evidence}


def _format_graph(records: list[dict]) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for rec in records:
        for node in rec.get("nodes", []):
            # Neo4j Python driver returns Node objects; labels is a frozenset,
            # properties are accessed via dict(node).
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
