import asyncio
from functools import partial

from fastembed.sparse.bm25 import Bm25
from sentence_transformers import SentenceTransformer
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Filter,
    FieldCondition,
    Fusion,
    FusionQuery,
    MatchValue,
    Prefetch,
    SparseVector,
)

from app.core.config import settings

_EMBED_MODEL = "all-MiniLM-L6-v2"


class QdrantService:
    _client: AsyncQdrantClient | None = None
    _encoder: SentenceTransformer | None = None
    _bm25: Bm25 | None = None

    def _get_client(self) -> AsyncQdrantClient:
        if self._client is None:
            self._client = AsyncQdrantClient(url=settings.qdrant_url)
        return self._client

    def _get_encoder(self) -> SentenceTransformer:
        if self._encoder is None:
            self._encoder = SentenceTransformer(_EMBED_MODEL)
        return self._encoder

    def _get_bm25(self) -> Bm25:
        if self._bm25 is None:
            self._bm25 = Bm25("Qdrant/bm25")
        return self._bm25

    async def _encode_dense(self, text: str) -> list[float]:
        loop = asyncio.get_running_loop()
        encoder = self._get_encoder()
        vector = await loop.run_in_executor(None, partial(encoder.encode, text))
        return vector.tolist()

    def _encode_sparse(self, text: str) -> SparseVector:
        bm25 = self._get_bm25()
        result = next(iter(bm25.query_embed(text)))
        return SparseVector(
            indices=result.indices.tolist(),
            values=result.values.tolist(),
        )

    async def search_text(self, query: str, collection: str, limit: int = 15) -> list[dict]:
        """Hybrid dense + BM25 sparse search fused via RRF.

        Falls back to dense-only search if the collection does not have
        named vectors (e.g. pre-Phase-3 lore_text schema).
        """
        dense_vector = await self._encode_dense(query)
        sparse_vector = self._encode_sparse(query)
        client = self._get_client()

        results = await client.query_points(
            collection_name=collection,
            prefetch=[
                Prefetch(query=dense_vector,  using="dense",  limit=limit * 2),
                Prefetch(query=sparse_vector, using="sparse", limit=limit * 2),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=limit,
            with_payload=True,
        )
        return [{"score": h.score, **h.payload} for h in results.points]

    async def search_by_vector(
        self,
        vector: list[float],
        collection: str,
        limit: int = 3,
        query_filter: Filter | None = None,
    ) -> list[dict]:
        client = self._get_client()
        hits = await client.search(
            collection_name=collection,
            query_vector=vector,
            limit=limit,
            query_filter=query_filter,
        )
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
