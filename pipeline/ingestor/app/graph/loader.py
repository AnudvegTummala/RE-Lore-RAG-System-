"""Neo4j entity loader.

Two-pass strategy:
  Pass 1 — MERGE every entity node from the markdown corpus. Each file
            maps to exactly one node; properties are set from frontmatter.
  Pass 2 — Delegate to relationship_builder to wire all edges. Doing this
            after all nodes exist avoids ordering dependencies.

A single AsyncDriver is created for the full run and shared across both
passes. A file-level checkpoint is maintained so the loader is idempotent:
re-running after a partial failure only processes the files that were not
yet completed.
"""

import logging
import os
import re
from pathlib import Path

from neo4j import AsyncGraphDatabase

from app.graph.relationship_builder import RelationshipBuilder
from app.utils.checkpoint import IngestCheckpoint
from app.utils.frontmatter import extract_frontmatter

logger = logging.getLogger(__name__)

_MARKDOWN_ROOT = Path("/data/raw/markdown")

_NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
_NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
_NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# entity_type value from frontmatter → Neo4j label
_LABEL_MAP: dict[str, str] = {
    "character":    "Character",
    "game":         "Game",
    "enemy":        "Enemy",
    "location":     "Location",
    "organization": "Organization",
    "virus":        "Virus",
    "weapon":       "Weapon",
    "timeline":     "TimelineEvent",
}

_MERGE_NODE = (
    "MERGE (n:{label} {{id: $id}}) "
    "SET n.title = $title, "
    "    n.source_url = $source_url, "
    "    n.entity_type = $entity_type, "
    "    n.franchise = $franchise, "
    "    n.scraped_at = $scraped_at, "
    "    n.tags = $tags"
)

# Writes all infobox key-value pairs as node properties. Keys are
# pre-sanitised in Python; SET n += map merges without touching other props.
_SET_INFOBOX = "MATCH (n:{label} {{id: $id}}) SET n += $props"


def _sanitise_infobox(infobox: dict) -> dict:
    """Return a copy of infobox with keys safe for use as Neo4j property names."""
    out = {}
    for k, v in infobox.items():
        # lowercase, replace runs of non-alphanumeric chars with underscore
        safe_key = re.sub(r"[^a-z0-9]+", "_", k.lower()).strip("_")
        if not safe_key:
            continue
        # Store as string so mixed-type infobox values don't upset Neo4j
        out[safe_key] = str(v) if not isinstance(v, (bool, int, float, list)) else v
    return out


async def load_graph() -> dict:
    """Run both passes. Returns a summary dict."""
    files = sorted(_MARKDOWN_ROOT.rglob("*.md"))
    logger.info("Graph loader: found %d markdown files", len(files))

    checkpoint = IngestCheckpoint("graph_loader")
    summary = {"nodes_created": 0, "nodes_skipped": 0, "relationships": 0, "errors": 0}

    async with AsyncGraphDatabase.driver(
        _NEO4J_URI, auth=(_NEO4J_USER, _NEO4J_PASSWORD)
    ) as driver:
        # --- Pass 1: create / update all nodes ---
        logger.info("Graph loader pass 1: upserting nodes...")
        docs: list[dict] = []
        async with driver.session() as session:
            for path in files:
                key = str(path)
                if checkpoint.is_done(key, phase="nodes"):
                    summary["nodes_skipped"] += 1
                    continue
                try:
                    fm, body = _load_file(path)
                    if not fm.get("id") or not fm.get("entity_type"):
                        logger.warning("Missing id/entity_type in %s, skipping", path.name)
                        continue

                    label = _LABEL_MAP.get(fm["entity_type"], "Entity")
                    await session.run(
                        _MERGE_NODE.format(label=label),
                        id=fm["id"],
                        title=fm.get("title", ""),
                        source_url=fm.get("source_url", ""),
                        entity_type=fm["entity_type"],
                        franchise=fm.get("franchise", "Resident Evil"),
                        scraped_at=fm.get("scraped_at", ""),
                        tags=fm.get("tags", []),
                    )
                    infobox = fm.get("infobox") or {}
                    if infobox:
                        props = _sanitise_infobox(infobox)
                        if props:
                            await session.run(
                                _SET_INFOBOX.format(label=label),
                                id=fm["id"],
                                props=props,
                            )
                    checkpoint.mark_done(key, phase="nodes")
                    summary["nodes_created"] += 1
                    docs.append({"frontmatter": fm, "body": body, "source_file": key})
                except Exception:
                    logger.exception("Node upsert failed for %s", path.name)
                    summary["errors"] += 1

        logger.info(
            "Graph loader pass 1 done: %d created, %d skipped, %d errors",
            summary["nodes_created"], summary["nodes_skipped"], summary["errors"],
        )

        # --- Pass 2: build relationships ---
        logger.info("Graph loader pass 2: building relationships...")
        builder = RelationshipBuilder(driver, checkpoint)
        rel_count = await builder.run(docs)
        summary["relationships"] = rel_count

    checkpoint.save()
    logger.info("Graph loader complete: %s", summary)
    return summary


def _load_file(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    fm, body = extract_frontmatter(text)
    return fm, body
