import asyncio
import random
import time
from urllib.parse import urlparse

MIN_GAP_SECONDS = 1.0
DEFAULT_DELAY_RANGE = (1.5, 3.0)


class RateLimiter:
    """Per-domain async rate limiter.

    Enforces a minimum 1-second gap between any two requests to the same
    domain, plus a randomised 1.5-3.0s jitter. Different domains do not
    block each other.
    """

    def __init__(
        self,
        min_gap: float = MIN_GAP_SECONDS,
        delay_range: tuple[float, float] = DEFAULT_DELAY_RANGE,
    ):
        self._min_gap = min_gap
        self._delay_range = delay_range
        self._last: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _domain_lock(self, domain: str) -> asyncio.Lock:
        lock = self._locks.get(domain)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[domain] = lock
        return lock

    async def wait(self, url: str) -> None:
        domain = urlparse(url).netloc or url
        async with self._domain_lock(domain):
            target_delay = max(self._min_gap, random.uniform(*self._delay_range))
            last = self._last.get(domain, 0.0)
            elapsed = time.monotonic() - last
            if elapsed < target_delay:
                await asyncio.sleep(target_delay - elapsed)
            self._last[domain] = time.monotonic()
