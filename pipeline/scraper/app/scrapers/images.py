import logging

import httpx

from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class ImageDownloader(BaseScraper):
    async def run(self, **kwargs) -> None:
        # Phase 2 implementation
        logger.info("ImageDownloader (stub) run")
