import asyncio
import logging
import os

from app.scrapers.fandom import FandomScraper
from app.scrapers.images import ImageDownloader
from app.scrapers.wikipedia import WikipediaScraper
from app.utils.manifests import ImageManifest, ScrapeManifest, SourceRegistry

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
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
