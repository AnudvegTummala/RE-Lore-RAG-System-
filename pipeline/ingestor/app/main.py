import asyncio
import logging
import os

from app.graph.schema import ensure_schema
from app.graph.loader import load_graph
from app.embeddings.text_embedder import embed_text_corpus
from app.embeddings.image_embedder import embed_image_corpus
from app.qdrant.collections import ensure_collections

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("Ingestor starting...")

    logger.info("Ensuring Neo4j schema...")
    await ensure_schema()

    logger.info("Ensuring Qdrant collections...")
    await ensure_collections()

    logger.info("Loading entities into Neo4j...")
    await load_graph()

    logger.info("Embedding text chunks into Qdrant...")
    await embed_text_corpus()

    logger.info("Embedding images into Qdrant...")
    await embed_image_corpus()

    logger.info("Ingestor finished.")


if __name__ == "__main__":
    asyncio.run(main())
