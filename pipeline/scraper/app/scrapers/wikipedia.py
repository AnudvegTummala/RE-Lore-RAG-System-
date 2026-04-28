import logging

import httpx

from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class WikipediaScraper(BaseScraper):
    async def run(self, target: str = "all") -> None:
        # Phase 2 implementation
        logger.info("WikipediaScraper (stub) run target=%s", target)
