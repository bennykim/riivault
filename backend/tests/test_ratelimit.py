import pytest

from riivault.collector.ratelimit import TokenBucket


class FakeClock:
    """Deterministic monotonic clock; sleeping advances virtual time."""

    def __init__(self) -> None:
        self.t = 0.0

    def monotonic(self) -> float:
        return self.t

    async def sleep(self, dt: float) -> None:
        self.t += dt


async def test_burst_up_to_capacity_incurs_no_wait():
    clock = FakeClock()
    bucket = TokenBucket(60, capacity=60, monotonic=clock.monotonic, sleep=clock.sleep)
    for _ in range(60):
        await bucket.acquire()
    assert clock.t == 0.0


async def test_per_minute_limit_forces_wait():
    clock = FakeClock()
    # 60/min => 1 token/sec, capacity 60. 60 burst + 60 throttled ~= 60s.
    bucket = TokenBucket(60, capacity=60, monotonic=clock.monotonic, sleep=clock.sleep)
    for _ in range(120):
        await bucket.acquire()
    assert clock.t == pytest.approx(60.0, abs=1e-6)


async def test_no_burst_capacity_one_spaces_calls():
    clock = FakeClock()
    # capacity 1 => no burst; 60/min => 1s between calls after the first.
    bucket = TokenBucket(60, capacity=1, monotonic=clock.monotonic, sleep=clock.sleep)
    for _ in range(6):
        await bucket.acquire()
    assert clock.t == pytest.approx(5.0, abs=1e-6)


async def test_higher_qpm_is_faster():
    clock = FakeClock()
    # 120/min => 2 tokens/sec. capacity 1 => 5 waits of 0.5s = 2.5s for 6 calls.
    bucket = TokenBucket(120, capacity=1, monotonic=clock.monotonic, sleep=clock.sleep)
    for _ in range(6):
        await bucket.acquire()
    assert clock.t == pytest.approx(2.5, abs=1e-6)


def test_invalid_rate_rejected():
    with pytest.raises(ValueError):
        TokenBucket(0)
