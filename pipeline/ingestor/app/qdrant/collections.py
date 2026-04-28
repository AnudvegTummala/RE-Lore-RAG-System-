import logging
import os

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

logger = logging.getLogger(__name__)

_QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")

_TEXT_DIM = 384
_CLIP_DIM = 512


async def ensure_collections() -> None:
    client = QdrantClient(url=_QDRANT_URL)
    existing = {c.name for c in client.get_collections().collections}

    if "lore_text" not in existing:
        client.create_collection(
            collection_name="lore_text",
            vectors_config=VectorParams(size=_TEXT_DIM, distance=Distance.COSINE),
        )
        logger.info("Created collection: lore_text")

    if "concept_art" not in existing:
        client.create_collection(
            collection_name="concept_art",
            vectors_config=VectorParams(size=_CLIP_DIM, distance=Distance.COSINE),
        )
        logger.info("Created collection: concept_art")
