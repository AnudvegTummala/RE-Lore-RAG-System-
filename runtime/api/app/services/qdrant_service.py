import asyncio
from functools import partial

from sentence_transformers import SentenceTransformer
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from app.core.config import settings

_EMBED_MODEL = "all-MiniLM-L6-v2"


class QdrantService:
    _client: AsyncQdrantClient | None = None
    _encoder: SentenceTransformer | None = None

    def _get_client(self) -> AsyncQdrantClient:
        if self._client is None:
            self._client = AsyncQdrantClient(url=settings.qdrant_url)
        return self._client

    def _get_encoder(self) -> SentenceTransformer:
        if self._encoder is None:
            self._encoder = SentenceTransformer(_EMBED_MODEL)
        return self._encoder

    async def _encode(self, text: str) -> list[float]:
        loop = asyncio.get_running_loop()
        encoder = self._get_encoder()
        vector = await loop.run_in_executor(None, partial(encoder.encode, text))
        return vector.tolist()

    async def search_text(self, query: str, collection: str, limit: int = 5) -> list[dict]:
        vector = await self._encode(query)
        client = self._get_client()
        hits = await client.search(collection_name=collection, query_vector=vector, limit=limit)
        return [{"score": h.score, **h.payload} for h in hits]

    async def search_by_vector(self, vector: list[float], collection: str, limit: int = 3) -> list[dict]:
        client = self._get_client()
        hits = await client.search(collection_name=collection, query_vector=vector, limit=limit)
        return [{"score": h.score, **h.payload} for h in hits]

    async def get_entity(self, entity_id: str) -> dict | None:
        client = self._get_client()
        results, _ = await client.scroll(
            collection_name="lore_text",
            scroll_filter=Filter(
                must=[FieldCondition(key="entity_id", match=MatchValue(value=entity_id))]
            ),
            limit=1,
            with_payload=True,
        )
        return dict(results[0].payload) if results else None


qdrant_service = QdrantService()
