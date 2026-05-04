import asyncio
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.scrapers.fandom import FandomScraper
from app.scrapers.images import ImageDownloader
from app.scrapers.wikipedia import WikipediaScraper
from app.utils.manifests import ImageManifest, ScrapeManifest, SourceRegistry

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_LOG_DIR = Path("/data/logs")
_LOG_FILE = _LOG_DIR / "scraper.log"
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
_BACKUP_COUNT = 5


def _configure_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO")
    fmt = logging.Formatter(_LOG_FORMAT)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(fmt)
    handlers: list[logging.Handler] = [stdout_handler]

    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            _LOG_FILE, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        handlers.append(file_handler)
    except OSError as e:
        logging.getLogger(__name__).warning("Could not open log file %s: %s", _LOG_FILE, e)

    logging.basicConfig(level=level, handlers=handlers)


_configure_logging()
logger = logging.getLogger(__name__)

TARGET = os.getenv("SCRAPE_TARGET", "all")
MAX_PAGES = int(os.getenv("MAX_PAGES", "500"))


async def main() -> None:
    logger.info("Scraper starting - target=%s max_pages=%d", TARGET, MAX_PAGES)

    image_manifest = ImageManifest()
    source_registry = SourceRegistry()
    scrape_manifest = ScrapeManifest()

    try:
        fandom = FandomScraper(
            image_manifest=image_manifest,
            source_registry=source_registry,
            scrape_manifest=scrape_manifest,
            max_pages=MAX_PAGES,
        )
        await fandom.run(target=TARGET)

        # Persist image refs collected during fandom run before downloading.
        image_manifest.save()
        source_registry.save()

        images = ImageDownloader(
            image_manifest=image_manifest,
            source_registry=source_registry,
            scrape_manifest=scrape_manifest,
        )
        await images.run()

        wiki = WikipediaScraper(
            source_registry=source_registry,
            scrape_manifest=scrape_manifest,
        )
        await wiki.run(target=TARGET)
    finally:
        image_manifest.save()
        source_registry.save()
        scrape_manifest.save()

    logger.info("Scraper finished.")


if __name__ == "__main__":
    asyncio.run(main())
