"""Async token-bucket rate limiter for Reddit QPM compliance.

The monotonic clock and sleep coroutine are injectable so the per-minute limit
can be verified deterministically with a fake clock in tests.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable


class TokenBucket:
    def __init__(
        self,
        rate_per_min: int,
        *,
        capacity: int | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        if rate_per_min <= 0:
            raise ValueError("rate_per_min must be positive")
        self.rate = rate_per_min / 60.0  # tokens per second
        self.capacity = float(capacity if capacity is not None else rate_per_min)
        self._tokens = self.capacity
        self._monotonic = monotonic
        self._sleep = sleep
        self._updated = monotonic()
        self._lock = asyncio.Lock()

    @property
    def tokens(self) -> float:
        return self._tokens

    def _refill(self) -> None:
        now = self._monotonic()
        elapsed = now - self._updated
        if elapsed > 0:
            self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
            self._updated = now

    async def acquire(self, n: int = 1) -> None:
        """Block until ``n`` tokens are available, then consume them."""
        async with self._lock:
            while True:
                self._refill()
                if self._tokens >= n:
                    self._tokens -= n
                    return
                deficit = n - self._tokens
                await self._sleep(deficit / self.rate)
