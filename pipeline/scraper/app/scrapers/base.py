import asyncio
import logging
from abc import ABC, abstractmethod

import httpx

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    def __init__(self, rate_delay: float = 2.0, max_pages: int = 500):
        self.rate_delay = rate_delay
        self.max_pages = max_pages

    async def fetch(self, client: httpx.AsyncClient, url: str, retries: int = 3) -> str | None:
        for attempt in range(retries):
            try:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                return response.text
            except httpx.HTTPError as exc:
                logger.warning("Fetch failed %s attempt %d: %s", url, attempt + 1, exc)
                if attempt < retries - 1:
                    await asyncio.sleep(self.rate_delay * (attempt + 1))
        return None

    @abstractmethod
    async def run(self, **kwargs) -> None: ...
