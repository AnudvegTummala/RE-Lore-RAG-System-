from app.schemas.source import Source


def build_citations(text_results: list[dict]) -> list[Source]:
    sources: list[Source] = []
    seen: set[str] = set()
    for r in text_results:
        entity_id = r.get("entity_id", "")
        if entity_id in seen:
            continue
        seen.add(entity_id)
        sources.append(
            Source(
                entity_id=entity_id,
                title=r.get("title", entity_id),
                section=r.get("section", ""),
                snippet=r.get("text", "")[:200],
                source_url=r.get("source_url", ""),
            )
        )
    return sources
