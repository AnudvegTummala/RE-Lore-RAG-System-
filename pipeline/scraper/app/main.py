import asyncio
import logging
import os

from app.scrapers.fandom import FandomScraper
from app.scrapers.wikipedia import WikipediaScraper
from app.scrapers.images import ImageDownloader

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

TARGET = os.getenv("SCRAPE_TARGET", "all")
RATE_DELAY = float(os.getenv("RATE_LIMIT_DELAY", "2.0"))
MAX_PAGES = int(os.getenv("MAX_PAGES", "500"))


async def main() -> None:
    logger.info("Scraper starting — target=%s max_pages=%d", TARGET, MAX_PAGES)

    fandom = FandomScraper(rate_delay=RATE_DELAY, max_pages=MAX_PAGES)
    wiki = WikipediaScraper(rate_delay=RATE_DELAY)
    images = ImageDownloader(rate_delay=RATE_DELAY)

    await fandom.run(target=TARGET)
    await wiki.run(target=TARGET)
    await images.run()

    logger.info("Scraper finished.")


if __name__ == "__main__":
    asyncio.run(main())
