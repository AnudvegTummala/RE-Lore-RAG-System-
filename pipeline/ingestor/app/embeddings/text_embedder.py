import logging
import os
from pathlib import Path

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from app.utils.markdown_loader import load_markdown_files
from app.utils.chunker import chunk_document

logger = logging.getLogger(__name__)

_QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
_EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
_MARKDOWN_ROOT = Path("/data/raw/markdown")


async def embed_text_corpus() -> None:
    encoder = SentenceTransformer(_EMBED_MODEL)
    client = QdrantClient(url=_QDRANT_URL)

    files = list(_MARKDOWN_ROOT.rglob("*.md"))
    logger.info("Embedding %d markdown files", len(files))

    points: list[PointStruct] = []
    idx = 0

    for path in files:
        try:
            doc = load_markdown_files(path)
            chunks = chunk_document(doc)
            for chunk in chunks:
                vector = encoder.encode(chunk["text"]).tolist()
                points.append(
                    PointStruct(
                        id=idx,
                        vector=vector,
                        payload=chunk,
                    )
                )
                idx += 1
        except Exception:
            logger.exception("Failed to embed %s", path)

    if points:
        client.upsert(collection_name="lore_text", points=points)
        logger.info("Upserted %d text chunks", len(points))
