import logging
import os
from pathlib import Path

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

logger = logging.getLogger(__name__)

_QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
_CLIP_URL = os.getenv("CLIP_SERVICE_URL", "http://localhost:8001")
_IMAGE_ROOT = Path("/data/raw/images")


async def embed_image_corpus() -> None:
    client = QdrantClient(url=_QDRANT_URL)
    image_files = list(_IMAGE_ROOT.rglob("*.jpg")) + list(_IMAGE_ROOT.rglob("*.png"))
    logger.info("Embedding %d images", len(image_files))

    points: list[PointStruct] = []
    idx = 0

    async with httpx.AsyncClient(timeout=30) as http:
        for path in image_files:
            try:
                image_bytes = path.read_bytes()
                response = await http.post(
                    f"{_CLIP_URL}/embed/image",
                    content=image_bytes,
                    headers={"Content-Type": "application/octet-stream"},
                )
                response.raise_for_status()
                vector = response.json()["vector"]
                category = path.parts[-2]
                points.append(
                    PointStruct(
                        id=idx,
                        vector=vector,
                        payload={
                            "image_path": str(path),
                            "entity_type": category,
                            "caption": path.stem.replace("-", " "),
                            "tags": [],
                        },
                    )
                )
                idx += 1
            except Exception:
                logger.exception("Failed to embed image %s", path)

    if points:
        client.upsert(collection_name="concept_art", points=points)
        logger.info("Upserted %d image embeddings", len(points))
