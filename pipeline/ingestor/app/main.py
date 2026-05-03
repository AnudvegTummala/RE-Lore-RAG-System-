import asyncio
import logging
import os

from app.graph.schema import ensure_schema
from app.graph.loader import load_graph
from app.graph.image_loader import load_images_into_graph
from app.graph.mention_extractor import extract_mentions
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

    logger.info("Step 1/7: ensuring Neo4j schema...")
    await ensure_schema()

    logger.info("Step 2/7: ensuring Qdrant collections...")
    await ensure_collections()

    logger.info("Step 3/7: loading entities and relationships into Neo4j...")
    graph_summary = await load_graph()
    logger.info("Graph summary: %s", graph_summary)

    logger.info("Step 4/7: embedding text chunks into Qdrant lore_text...")
    text_summary = await embed_text_corpus()
    logger.info("Text embedding summary: %s", text_summary)

    logger.info("Step 5/7: embedding images into Qdrant concept_art...")
    image_summary = await embed_image_corpus()
    logger.info("Image embedding summary: %s", image_summary)

    logger.info("Step 6/7: loading ConceptArt nodes and HAS_IMAGE edges into Neo4j...")
    image_graph_summary = await load_images_into_graph()
    logger.info("Image graph summary: %s", image_graph_summary)

    logger.info("Step 7/7: extracting MENTIONS relationships from entity bodies...")
    mentions_summary = await extract_mentions()
    logger.info("Mentions summary: %s", mentions_summary)

    logger.info(
        "Ingestor finished. Graph: %s | Text: %s | Images: %s | Image graph: %s | Mentions: %s",
        graph_summary, text_summary, image_summary, image_graph_summary, mentions_summary,
    )


if __name__ == "__main__":
    asyncio.run(main())
