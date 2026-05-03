"""Mention extractor — pass 5 of the graph pipeline.

Scans each entity's markdown body for references to other known entity
titles and creates MENTIONS relationships in Neo4j.

Strategy:
1. Load all entity (id, title) pairs from Neo4j into a lookup table.
2. Sort titles longest-first so multi-word titles match before their
   substrings (e.g. "Albert Wesker" before "Wesker").
3. For each source entity body, scan for title occurrences (case-insensitive).
   Skip self-references. MERGE each found (source)-[:MENTIONS]->(target).
4. Checkpoint-gated per source entity_id so re-runs are idempotent.

Minimum title length of 4 characters guards against false positives from
very short names (e.g. "Ada", "G").
"""

import logging
import os
import re
from pathlib import Path

from neo4j import AsyncGraphDatabase

from app.utils.checkpoint import IngestCheckpoint
from app.utils.frontmatter import extract_frontmatter

logger = logging.getLogger(__name__)

_NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
_NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
_NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
_MARKDOWN_ROOT = Path("/data/raw/markdown")
_MIN_TITLE_LEN = 4

_FETCH_TITLES = "MATCH (n) WHERE n.id IS NOT NULL AND n.title IS NOT NULL RETURN n.id AS id, n.title AS title"

_MERGE_MENTIONS = (
    "MATCH (a {id: $from_id}), (b {id: $to_id}) "
    "MERGE (a)-[:MENTIONS]->(b)"
)


def _build_lookup(records: list) -> list[tuple[str, str, re.Pattern]]:
    """Return list of (id, title, compiled_pattern) sorted longest title first."""
    entries = []
    for r in records:
        title = r["title"]
        if not title or len(title) < _MIN_TITLE_LEN:
            continue
        pattern = re.compile(r"\b" + re.escape(title) + r"\b", re.IGNORECASE)
        entries.append((r["id"], title, pattern))
    entries.sort(key=lambda x: len(x[1]), reverse=True)
    return entries


async def extract_mentions() -> dict:
    files = sorted(_MARKDOWN_ROOT.rglob("*.md"))
    logger.info("Mention extractor: %d markdown files to scan", len(files))

    checkpoint = IngestCheckpoint("mention_extractor")
    summary = {"entities_scanned": 0, "mentions_created": 0, "skipped": 0, "errors": 0}

    async with AsyncGraphDatabase.driver(
        _NEO4J_URI, auth=(_NEO4J_USER, _NEO4J_PASSWORD)
    ) as driver:
        async with driver.session() as session:
            result = await session.run(_FETCH_TITLES)
            records = await result.data()

        lookup = _build_lookup(records)
        logger.info("Mention extractor: %d entity titles loaded for matching", len(lookup))

        async with driver.session() as session:
            for path in files:
                text = path.read_text(encoding="utf-8")
                fm, body = extract_frontmatter(text)
                source_id = fm.get("id")
                if not source_id:
                    continue
                if checkpoint.is_done(source_id, phase="mentions"):
                    summary["skipped"] += 1
                    continue

                try:
                    for target_id, _title, pattern in lookup:
                        if target_id == source_id:
                            continue
                        if pattern.search(body):
                            await session.run(
                                _MERGE_MENTIONS,
                                from_id=source_id,
                                to_id=target_id,
                            )
                            summary["mentions_created"] += 1

                    checkpoint.mark_done(source_id, phase="mentions")
                    summary["entities_scanned"] += 1
                except Exception:
                    logger.exception("Mention extraction failed for %s", source_id)
                    summary["errors"] += 1

    checkpoint.save()
    logger.info(
        "Mention extractor done: %d scanned, %d mentions, %d skipped, %d errors",
        summary["entities_scanned"], summary["mentions_created"],
        summary["skipped"], summary["errors"],
    )
    return summary
