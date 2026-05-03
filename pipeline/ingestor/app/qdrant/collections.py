import logging
import os

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    PayloadSchemaType,
    SparseIndexParams,
    SparseVectorParams,
    VectorParams,
)

logger = logging.getLogger(__name__)

_QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")

_TEXT_DIM = 384
_CLIP_DIM = 512


async def ensure_collections() -> None:
    client = AsyncQdrantClient(url=_QDRANT_URL)
    existing = {c.name for c in (await client.get_collections()).collections}

    if "lore_text" not in existing:
        await client.create_collection(
            collection_name="lore_text",
            vectors_config={"dense": VectorParams(size=_TEXT_DIM, distance=Distance.COSINE)},
            sparse_vectors_config={"sparse": SparseVectorParams(index=SparseIndexParams(on_disk=False))},
        )
        logger.info("Created collection: lore_text")

    # Payload index on entity_id so graph_retrieval can filter by entity efficiently.
    await client.create_payload_index(
        collection_name="lore_text",
        field_name="entity_id",
        field_schema=PayloadSchemaType.KEYWORD,
    )

    if "concept_art" not in existing:
        await client.create_collection(
            collection_name="concept_art",
            vectors_config=VectorParams(size=_CLIP_DIM, distance=Distance.COSINE),
        )
        logger.info("Created collection: concept_art")

    await client.create_payload_index(
        collection_name="concept_art",
        field_name="entity_id",
        field_schema=PayloadSchemaType.KEYWORD,
    )

    logger.info("Qdrant collections ready")
