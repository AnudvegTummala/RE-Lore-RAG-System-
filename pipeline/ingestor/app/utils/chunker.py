import re


def chunk_document(doc: dict, max_chars: int = 800) -> list[dict]:
    fm = doc.get("frontmatter", {})
    body = doc.get("body", "")
    source_file = doc.get("source_file", "")

    sections = re.split(r"\n#{1,3} ", body)
    chunks: list[dict] = []
    chunk_idx = 0

    for section in sections:
        section = section.strip()
        if not section:
            continue
        heading_match = re.match(r"^(.+?)\n", section)
        section_name = heading_match.group(1).strip() if heading_match else "General"

        paragraphs = section.split("\n\n")
        current = ""
        for para in paragraphs:
            if len(current) + len(para) + 2 > max_chars and current:
                chunks.append(_make_chunk(fm, section_name, current, source_file, chunk_idx))
                chunk_idx += 1
                current = para
            else:
                current = f"{current}\n\n{para}" if current else para
        if current.strip():
            chunks.append(_make_chunk(fm, section_name, current, source_file, chunk_idx))
            chunk_idx += 1

    return chunks


def _make_chunk(fm: dict, section: str, text: str, source_file: str, idx: int) -> dict:
    entity_id = fm.get("id", "unknown")
    return {
        "chunk_id": f"{entity_id}_{section.lower().replace(' ', '_')}_{idx:03d}",
        "entity_id": entity_id,
        "entity_type": fm.get("entity_type", ""),
        "title": fm.get("title", ""),
        "section": section,
        "source_file": source_file,
        "source_url": fm.get("source_url", ""),
        "tags": fm.get("tags", []),
        "text": text.strip(),
    }
