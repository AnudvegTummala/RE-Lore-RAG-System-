import logging

import httpx
from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper
from app.utils.checkpoint import Checkpoint
from app.utils.markdown_writer import MarkdownWriter
from app.utils.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

_BASE_URL = "https://residentevil.fandom.com/wiki"

_CATEGORY_URLS: dict[str, str] = {
    "characters": f"{_BASE_URL}/Category:Characters",
    "games": f"{_BASE_URL}/Category:Games",
    "enemies": f"{_BASE_URL}/Category:Enemies",
    "locations": f"{_BASE_URL}/Category:Locations",
    "organizations": f"{_BASE_URL}/Category:Organizations",
    "timeline": f"{_BASE_URL}/Category:Timeline",
}


class FandomScraper(BaseScraper):
    async def run(self, target: str = "all") -> None:
        categories = (
            _CATEGORY_URLS
            if target == "all"
            else {target: _CATEGORY_URLS[target]}
        )

        checkpoint = Checkpoint("scraper_state")
        writer = MarkdownWriter()
        limiter = RateLimiter(self.rate_delay)

        headers = {"User-Agent": "RE-Lore-Oracle-Scraper/0.1 (research project)"}

        async with httpx.AsyncClient(headers=headers, timeout=30) as client:
            for category, url in categories.items():
                logger.info("Scraping category: %s", category)
                await self._scrape_category(client, category, url, checkpoint, writer, limiter)

    async def _scrape_category(self, client, category, url, checkpoint, writer, limiter):
        # Phase 2 implementation
        logger.info("  (stub) _scrape_category %s -> %s", category, url)
