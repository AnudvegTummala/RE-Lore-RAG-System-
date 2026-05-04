"""Image loader — pass 4 of the graph pipeline.

Reads image_manifest.json and creates ConceptArt nodes in Neo4j, then
wires HAS_IMAGE relationships from each owning entity to its images.

Designed to be idempotent: MERGE semantics mean re-runs only update
properties rather than duplicating nodes. Checkpoint-gated per image_id
so a crash mid-run resumes cleanly without redoing completed work.
"""

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from neo4j import AsyncGraphDatabase

from app.utils.checkpoint import IngestCheckpoint

if TYPE_CHECKING:
    from neo4j import AsyncDriver

logger = logging.getLogger(__name__)

_NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
_NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
_NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
_MANIFEST_PATH = Path("/data/raw/manifests/image_manifest.json")

_MERGE_CONCEPT_ART = """
MERGE (n:ConceptArt {id: $image_id})
SET n.entity_id   = $entity_id,
    n.entity_type = $entity_type,
    n.image_path  = $image_path,
    n.caption     = $caption,
    n.section     = $section,
    n.width       = $width,
    n.height      = $height
"""

# Generic MATCH on id regardless of entity label — works for all entity types.
_MERGE_HAS_IMAGE = """
MATCH (e {id: $entity_id})
MATCH (n:ConceptArt {id: $image_id})
MERGE (e)-[:HAS_IMAGE]->(n)
"""


async def load_images_into_graph() -> dict:
    if not _MANIFEST_PATH.exists():
        logger.warning("Image manifest not found at %s, skipping image graph load", _MANIFEST_PATH)
        return {"nodes_created": 0, "edges_created": 0, "skipped": 0, "errors": 0}

    manifest: dict = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    pending = [
        (image_id, meta)
        for image_id, meta in manifest.items()
        if meta.get("local_path") and not meta.get("skipped")
    ]
    logger.info(
        "Image graph loader: %d total images, %d downloaded to process",
        len(manifest), len(pending),
    )

    checkpoint = IngestCheckpoint("image_loader")
    summary = {"nodes_created": 0, "edges_created": 0, "skipped": 0, "errors": 0}

    async with AsyncGraphDatabase.driver(
        _NEO4J_URI, auth=(_NEO4J_USER, _NEO4J_PASSWORD)
    ) as driver:
        async with driver.session() as session:
            for image_id, meta in pending:
                if checkpoint.is_done(image_id, phase="image_node"):
                    summary["skipped"] += 1
                    continue
                try:
                    await session.run(
                        _MERGE_CONCEPT_ART,
                        image_id=image_id,
                        entity_id=meta.get("entity_id", ""),
                        entity_type=meta.get("entity_type", ""),
                        image_path=meta.get("local_path", ""),
                        caption=meta.get("caption") or meta.get("alt_text", ""),
                        section=meta.get("section", ""),
                        width=meta.get("width"),
                        height=meta.get("height"),
                    )
                    summary["nodes_created"] += 1

                    entity_id = meta.get("entity_id", "")
                    if entity_id:
                        await session.run(
                            _MERGE_HAS_IMAGE,
                            entity_id=entity_id,
                            image_id=image_id,
                        )
                        summary["edges_created"] += 1

                    checkpoint.mark_done(image_id, phase="image_node")
                except Exception:
                    logger.exception("Image graph load failed for %s", image_id)
                    summary["errors"] += 1

    checkpoint.save()
    logger.info(
        "Image graph loader done: %d nodes, %d edges, %d skipped, %d errors",
        summary["nodes_created"], summary["edges_created"],
        summary["skipped"], summary["errors"],
    )
    return summary
