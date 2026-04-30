"""Text embedder — populates the ``lore_text`` Qdrant collection.

Loads every markdown file from the corpus, runs the hierarchical chunker
to produce parent-child chunk pairs, embeds each child chunk with
``all-MiniLM-L6-v2`` (dim=384), and upserts into Qdrant.

Key design decisions:
- SentenceTransformer.encode() is CPU/GPU-bound; it runs in a thread
  executor so it doesn't block the asyncio event loop.
- Qdrant upsert uses the async client throughout.
- Points use UUID5 IDs derived from chunk_id so they are stable across
  re-runs (upsert is idempotent for existing points).
- A file-level checkpoint skips already-embedded files on restart.
- Embedding is batched (BATCH_SIZE chunks at a time) to avoid OOM on
  large corpora.
"""

import asyncio
import logging
import os
import uuid
from functools import partial
from pathlib import Path

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct
from sentence_transformers import SentenceTransformer

from app.utils.checkpoint import IngestCheckpoint
from app.utils.chunker import chunk_document
from app.utils.markdown_loader import load_markdown_file

logger = logging.getLogger(__name__)

_QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
_EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
_MARKDOWN_ROOT = Path("/data/raw/markdown")
_COLLECTION = "lore_text"
_BATCH_SIZE = 64

# Stable UUID namespace for chunk point IDs.
_UUID_NS = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def _chunk_uuid(chunk_id: str) -> str:
    return str(uuid.uuid5(_UUID_NS, chunk_id))


async def embed_text_corpus() -> dict:
    logger.info("Text embedder: loading model %s", _EMBED_MODEL)
    loop = asyncio.get_running_loop()
    encoder = await loop.run_in_executor(None, SentenceTransformer, _EMBED_MODEL)

    client = AsyncQdrantClient(url=_QDRANT_URL)
    checkpoint = IngestCheckpoint("text_embedder")

    files = sorted(_MARKDOWN_ROOT.rglob("*.md"))
    logger.info("Text embedder: %d markdown files to process", len(files))

    summary = {"files_processed": 0, "files_skipped": 0, "chunks_upserted": 0, "errors": 0}

    batch_chunks: list[dict] = []

    async def flush_batch() -> None:
        if not batch_chunks:
            return
        texts = [c["chunk_text"] for c in batch_chunks]
        encode_fn = partial(encoder.encode, texts, show_progress_bar=False)
        vectors = await loop.run_in_executor(None, encode_fn)
        points = [
            PointStruct(
                id=_chunk_uuid(c["chunk_id"]),
                vector=vectors[i].tolist(),
                payload={
                    "chunk_id":    c["chunk_id"],
                    "entity_id":   c["entity_id"],
                    "entity_type": c["entity_type"],
                    "title":       c["title"],
                    "section":     c["section"],
                    "source_file": c["source_file"],
                    "source_url":  c["source_url"],
                    "tags":        c["tags"],
                    "chunk_text":  c["chunk_text"],
                    "parent_text": c["parent_text"],
                },
            )
            for i, c in enumerate(batch_chunks)
        ]
        await client.upsert(collection_name=_COLLECTION, points=points)
        summary["chunks_upserted"] += len(points)
        batch_chunks.clear()

    for path in files:
        key = str(path)
        if checkpoint.is_done(key, phase="text_embed"):
            summary["files_skipped"] += 1
            continue
        try:
            doc = load_markdown_file(path)
            chunks = chunk_document(doc)
            batch_chunks.extend(chunks)
            if len(batch_chunks) >= _BATCH_SIZE:
                await flush_batch()
            checkpoint.mark_done(key, phase="text_embed")
            summary["files_processed"] += 1
        except Exception:
            logger.exception("Text embed failed for %s", path.name)
            summary["errors"] += 1

    await flush_batch()
    checkpoint.save()

    logger.info(
        "Text embedder done: %d files processed, %d skipped, %d chunks upserted, %d errors",
        summary["files_processed"], summary["files_skipped"],
        summary["chunks_upserted"], summary["errors"],
    )
    return summary
