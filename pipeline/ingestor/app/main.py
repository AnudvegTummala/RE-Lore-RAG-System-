import asyncio
import logging
import os

from app.graph.schema import ensure_schema
from app.graph.loader import load_graph
from app.embeddings.text_embedder import embed_text_corpus
from app.embeddings.image_embedder import embed_image_corpus
from app.qdrant.collections import ensure_collections

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("Ingestor starting...")

    logger.info("Step 1/5: ensuring Neo4j schema...")
    await ensure_schema()

    logger.info("Step 2/5: ensuring Qdrant collections...")
    await ensure_collections()

    logger.info("Step 3/5: loading entities and relationships into Neo4j...")
    graph_summary = await load_graph()
    logger.info("Graph summary: %s", graph_summary)

    logger.info("Step 4/5: embedding text chunks into Qdrant lore_text...")
    text_summary = await embed_text_corpus()
    logger.info("Text embedding summary: %s", text_summary)

    logger.info("Step 5/5: embedding images into Qdrant concept_art...")
    image_summary = await embed_image_corpus()
    logger.info("Image embedding summary: %s", image_summary)

    logger.info(
        "Ingestor finished. Graph: %s | Text: %s | Images: %s",
        graph_summary, text_summary, image_summary,
    )


if __name__ == "__main__":
    asyncio.run(main())
