import asyncio
import time


class RateLimiter:
    def __init__(self, delay: float = 2.0):
        self.delay = delay
        self._last = 0.0

    async def wait(self) -> None:
        elapsed = time.monotonic() - self._last
        if elapsed < self.delay:
            await asyncio.sleep(self.delay - elapsed)
        self._last = time.monotonic()
