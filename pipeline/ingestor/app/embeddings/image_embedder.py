"""Image embedder — populates the ``concept_art`` Qdrant collection.

Reads image_manifest.json for all downloaded images (those with a
``local_path``), POSTs each to the CLIP service for embedding, and
upserts the resulting 512-dim vector into Qdrant.

Key design decisions:
- Only images with a ``local_path`` (successfully downloaded) are embedded.
- UUID5 IDs derived from image_id for stable idempotent upserts.
- Per-image checkpoint so a crash mid-run doesn't re-embed everything.
- Concurrency capped at 4 simultaneous CLIP requests to avoid overwhelming
  the service (it loads one model and processes sequentially internally).
"""

import asyncio
import json
import logging
import os
import uuid
from pathlib import Path

import httpx
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct

from app.utils.checkpoint import IngestCheckpoint

logger = logging.getLogger(__name__)

_QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
_CLIP_URL = os.getenv("CLIP_SERVICE_URL", "http://localhost:8001")
_MANIFEST_PATH = Path("/data/state/image_manifest.json")
_COLLECTION = "concept_art"
_CONCURRENCY = 4

_UUID_NS = uuid.UUID("b2c3d4e5-f6a7-8901-bcde-f12345678901")


def _image_uuid(image_id: str) -> str:
    return str(uuid.uuid5(_UUID_NS, image_id))


async def embed_image_corpus() -> dict:
    if not _MANIFEST_PATH.exists():
        logger.warning("Image manifest not found at %s, skipping image embedding", _MANIFEST_PATH)
        return {"images_embedded": 0, "images_skipped": 0, "errors": 0}

    manifest: dict = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    entries = manifest.get("images", {})

    pending = [
        (image_id, meta)
        for image_id, meta in entries.items()
        if meta.get("local_path") and not meta.get("skipped")
    ]
    logger.info(
        "Image embedder: %d total images, %d with local_path to embed",
        len(entries), len(pending),
    )

    client = AsyncQdrantClient(url=_QDRANT_URL)
    checkpoint = IngestCheckpoint("image_embedder")
    semaphore = asyncio.Semaphore(_CONCURRENCY)
    summary = {"images_embedded": 0, "images_skipped": 0, "errors": 0}

    async with httpx.AsyncClient(timeout=60) as http:
        tasks = [
            _embed_one(http, client, checkpoint, semaphore, summary, image_id, meta)
            for image_id, meta in pending
        ]
        await asyncio.gather(*tasks, return_exceptions=False)

    checkpoint.save()
    logger.info(
        "Image embedder done: %d embedded, %d skipped, %d errors",
        summary["images_embedded"], summary["images_skipped"], summary["errors"],
    )
    return summary


async def _embed_one(
    http: httpx.AsyncClient,
    qdrant: AsyncQdrantClient,
    checkpoint: IngestCheckpoint,
    semaphore: asyncio.Semaphore,
    summary: dict,
    image_id: str,
    meta: dict,
) -> None:
    if checkpoint.is_done(image_id, phase="image_embed"):
        summary["images_skipped"] += 1
        return

    local_path = Path(meta["local_path"])
    if not local_path.exists():
        logger.warning("Image file missing: %s", local_path)
        summary["images_skipped"] += 1
        return

    async with semaphore:
        try:
            image_bytes = local_path.read_bytes()
            response = await http.post(
                f"{_CLIP_URL}/embed/image",
                content=image_bytes,
                headers={"Content-Type": "application/octet-stream"},
            )
            response.raise_for_status()
            vector = response.json()["vector"]

            point = PointStruct(
                id=_image_uuid(image_id),
                vector=vector,
                payload={
                    "image_id":    image_id,
                    "entity_id":   meta.get("entity_id", ""),
                    "entity_type": meta.get("entity_type", ""),
                    "image_path":  str(local_path),
                    "caption":     meta.get("alt_text", ""),
                    "tags":        [],
                },
            )
            await qdrant.upsert(collection_name=_COLLECTION, points=[point])
            checkpoint.mark_done(image_id, phase="image_embed")
            summary["images_embedded"] += 1
        except Exception:
            logger.exception("Image embed failed for %s", image_id)
            summary["errors"] += 1
