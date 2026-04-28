def extract_entity(doc: dict) -> dict:
    fm = doc.get("frontmatter", {})
    return {
        "id": fm.get("id", ""),
        "entity_type": fm.get("entity_type", ""),
        "title": fm.get("title", ""),
        "source_url": fm.get("source_url", ""),
        "tags": fm.get("tags", []),
        "related_games": fm.get("related_games", []),
        "image_refs": fm.get("image_refs", []),
        "body": doc.get("body", ""),
        "frontmatter": fm,
    }
