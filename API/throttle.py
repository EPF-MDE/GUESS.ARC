"""Per-provider minimum interval between calls (issue #12).

Pure pacing logic — clock and sleep are injected, so it is unit-testable
without real waiting (see test/test_benchmark_scheduling.py), same split as
provider_fallback.py.
"""
from __future__ import annotations

import time
from typing import Callable


class Throttle:
    """`wait(key, min_interval_s)` blocks until at least `min_interval_s`
    seconds have passed since the previous `wait` on the same `key`, then
    stamps the current time. The first call on a key never waits."""

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        sleep_fn: Callable[[float], None] = time.sleep,
    ):
        self._clock = clock
        self._sleep = sleep_fn
        self._last: dict[str, float] = {}

    def wait(self, key: str, min_interval_s: float) -> None:
        last = self._last.get(key)
        if last is not None:
            remaining = last + min_interval_s - self._clock()
            if remaining > 0:
                self._sleep(remaining)
        self._last[key] = self._clock()
