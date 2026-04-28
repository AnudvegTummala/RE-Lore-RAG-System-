import logging
from pathlib import Path

from app.utils.markdown_loader import load_markdown_files
from app.graph.entity_extractor import extract_entity
from app.graph.relationship_builder import build_relationships

logger = logging.getLogger(__name__)

_MARKDOWN_ROOT = Path("/data/raw/markdown")


async def load_entities() -> None:
    files = list(_MARKDOWN_ROOT.rglob("*.md"))
    logger.info("Found %d markdown files", len(files))

    for path in files:
        try:
            doc = load_markdown_files(path)
            entity = extract_entity(doc)
            await build_relationships(entity)
        except Exception:
            logger.exception("Failed to load %s", path)
