"""Hierarchical parent-child chunker with contextual prefixing.

Strategy
--------
For each markdown section (split by ## headings):

1. The full section text (trimmed to PARENT_MAX_CHARS) is the *parent* —
   stored in the Qdrant payload and returned to the LLM at query time.

2. The parent is sub-split into *child* chunks (≤ CHILD_MAX_CHARS) by
   sentence boundary. Each child is prefixed with "{title} — {section}: "
   before embedding so the vector carries entity context in isolation
   (contextual retrieval).

Each returned dict represents one Qdrant point:
  chunk_id    — stable ID: "{entity_id}_{section_slug}_{idx:03d}"
  chunk_text  — prefixed child text (what gets embedded)
  parent_text — full section text (returned to LLM)
  section     — heading name
  entity_id / entity_type / title / source_file / source_url / tags
"""

import re

CHILD_MAX_CHARS = 400
PARENT_MAX_CHARS = 1500

# Sentence boundary: end of sentence followed by whitespace or end of string.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def chunk_document(doc: dict) -> list[dict]:
    fm = doc.get("frontmatter", {})
    body = doc.get("body", "")
    source_file = doc.get("source_file", "")
    title = fm.get("title", "Unknown")

    sections = _split_sections(body)
    chunks: list[dict] = []
    chunk_idx = 0

    for section_name, section_text in sections:
        section_text = section_text.strip()
        if not section_text:
            continue

        parent_text = section_text[:PARENT_MAX_CHARS].strip()
        prefix = f"{title} — {section_name}: "

        children = _split_children(section_text, prefix)
        for child_text in children:
            chunks.append(
                _make_chunk(fm, section_name, child_text, parent_text, source_file, chunk_idx)
            )
            chunk_idx += 1

    return chunks


def _split_sections(body: str) -> list[tuple[str, str]]:
    """Return [(section_name, section_text), ...] split on ## headings.

    The preamble before the first heading is yielded as "Summary".
    The document title (# heading) is stripped.
    """
    # Strip the top-level # title line
    body = re.sub(r"^#[^#][^\n]*\n", "", body.lstrip())

    sections: list[tuple[str, str]] = []
    # Split on ## or ### headings
    parts = re.split(r"\n(#{2,3} .+)\n", body)

    # parts[0] is preamble, then alternating [heading, content, heading, content, ...]
    preamble = parts[0].strip()
    if preamble:
        sections.append(("Summary", preamble))

    i = 1
    while i < len(parts) - 1:
        heading = parts[i].lstrip("#").strip()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if content:
            sections.append((heading, content))
        i += 2

    return sections


def _last_sentence(text: str) -> str:
    """Return the last sentence of text, or the whole text if no boundary found."""
    parts = _SENTENCE_END.split(text.strip())
    return parts[-1].strip() if parts else text.strip()


def _split_children(text: str, prefix: str) -> list[str]:
    """Sub-split section text into prefixed child chunks ≤ CHILD_MAX_CHARS.

    Splits on sentence boundaries where possible; falls back to hard split
    if a single sentence exceeds the limit. Each chunk opens with the last
    sentence of the previous chunk so context is not lost at boundaries.
    """
    budget = CHILD_MAX_CHARS - len(prefix)
    if budget <= 0:
        # Prefix alone fills the budget — just return one hard-truncated chunk
        return [prefix + text[:CHILD_MAX_CHARS - len(prefix)]]

    sentences = _SENTENCE_END.split(text)
    children: list[str] = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        # Single sentence exceeds budget — hard split it
        if len(sentence) > budget:
            if current:
                overlap = _last_sentence(current)
                children.append(prefix + current.strip())
                current = overlap
            for start in range(0, len(sentence), budget):
                children.append(prefix + sentence[start : start + budget])
            continue

        if current and len(current) + 1 + len(sentence) > budget:
            overlap = _last_sentence(current)
            children.append(prefix + current.strip())
            current = f"{overlap} {sentence}" if overlap else sentence
        else:
            current = f"{current} {sentence}" if current else sentence

    if current.strip():
        children.append(prefix + current.strip())

    return children if children else [prefix + text[:budget]]


def _make_chunk(
    fm: dict,
    section: str,
    chunk_text: str,
    parent_text: str,
    source_file: str,
    idx: int,
) -> dict:
    entity_id = fm.get("id", "unknown")
    section_slug = re.sub(r"[^a-z0-9]+", "_", section.lower()).strip("_")
    return {
        "chunk_id": f"{entity_id}_{section_slug}_{idx:03d}",
        "entity_id": entity_id,
        "entity_type": fm.get("entity_type", ""),
        "title": fm.get("title", ""),
        "section": section,
        "source_file": source_file,
        "source_url": fm.get("source_url", ""),
        "tags": fm.get("tags", []),
        "chunk_text": chunk_text,
        "parent_text": parent_text,
    }
