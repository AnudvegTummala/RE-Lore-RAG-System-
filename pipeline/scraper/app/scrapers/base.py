import asyncio
import logging
from abc import ABC, abstractmethod

import httpx

from app.utils.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; RE-Lore-Oracle-Research-Bot/1.0)"
DEFAULT_HEADERS = {"User-Agent": USER_AGENT}

MAX_CONCURRENT_REQUESTS = 5
MAX_RETRIES = 5
MAX_BACKOFF_SECONDS = 64
RETRYABLE_STATUS_CODES = {429, 403, 503}

_GLOBAL_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
_GLOBAL_LIMITER = RateLimiter()


class FetchError(Exception):
    """Raised when a URL fetch exhausts all retries."""


class BaseScraper(ABC):
    """Shared HTTP fetch infrastructure for all scrapers.

    All concrete scrapers share a single global semaphore (max 5 concurrent
    requests) and a single global rate limiter. The fetch method performs
    exponential backoff (2^attempt seconds, capped at 64s) on retryable
    statuses (429, 403, 503) and on transport errors, up to MAX_RETRIES
    attempts. Permanent failures are logged and return None.
    """

    def __init__(self, max_pages: int = 500):
        self.max_pages = max_pages
        self.headers = dict(DEFAULT_HEADERS)
        self.limiter = _GLOBAL_LIMITER
        self.semaphore = _GLOBAL_SEMAPHORE

    def build_client(self, timeout: float = 30.0) -> httpx.AsyncClient:
        return httpx.AsyncClient(headers=self.headers, timeout=timeout, http2=True)

    async def fetch(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        binary: bool = False,
    ) -> str | bytes | None:
        for attempt in range(MAX_RETRIES):
            async with self.semaphore:
                await self.limiter.wait(url)
                try:
                    response = await client.get(url, follow_redirects=True)
                except httpx.RequestError as exc:
                    backoff = min(2 ** attempt, MAX_BACKOFF_SECONDS)
                    logger.warning(
                        "Network error on %s (attempt %d/%d): %s; backoff %.1fs",
                        url, attempt + 1, MAX_RETRIES, exc, backoff,
                    )
                    await asyncio.sleep(backoff)
                    continue

            if 200 <= response.status_code < 300:
                return response.content if binary else response.text

            if response.status_code in RETRYABLE_STATUS_CODES:
                backoff = min(2 ** attempt, MAX_BACKOFF_SECONDS)
                logger.warning(
                    "HTTP %d on %s (attempt %d/%d); backoff %.1fs",
                    response.status_code, url, attempt + 1, MAX_RETRIES, backoff,
                )
                await asyncio.sleep(backoff)
                continue

            logger.warning(
                "Non-retryable HTTP %d on %s; giving up",
                response.status_code, url,
            )
            return None

        logger.error("Exhausted %d retries on %s", MAX_RETRIES, url)
        return None

    @abstractmethod
    async def run(self, **kwargs) -> None: ...
