"""Generic provider fallback mechanism (issue #6).

Pure retry/fallback logic, no HTTP and no real sleeping — `call_fn` and
`sleep_fn` are injected, so this is unit-testable without network access
(see test/test_provider_fallback.py). The HTTP layer (taxonomy_client.py)
is the only place that knows about `requests`/status codes; it reports
failures here via ProviderCallError.

Reusable as-is by future providers (#7 Groq, #8 OpenRouter): adding a
provider means extending providers.FALLBACK_CHAIN, never adding a branch
here.
"""
from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")

# "backoff exponentiel plafonné à ~120s" (issue #6 acceptance criteria).
MAX_BACKOFF_SECONDS = 120.0

# Safety caps on in-place retries before giving up on the current provider
# and moving to the next one in the chain.
MAX_429_ATTEMPTS = 5
MAX_5XX_ATTEMPTS = 1


class ProviderCallError(Exception):
    """Raised by a call_fn to report an HTTP failure the retry/fallback loop
    can act on. `retry_after` is the provider's Retry-After value in seconds,
    if any (None means "no such header, use backoff instead")."""

    def __init__(self, status_code: int, retry_after: float | None = None, message: str = ""):
        super().__init__(message or f"provider call failed with status {status_code}")
        self.status_code = status_code
        self.retry_after = retry_after


class AllProvidersFailedError(Exception):
    """Every provider in the chain was tried and exhausted its retries."""

    def __init__(self, errors: dict[str, Exception]):
        self.errors = errors
        detail = "; ".join(f"{name}: {err}" for name, err in errors.items())
        super().__init__(f"all providers failed: {detail}")


def backoff_seconds(attempt: int) -> float:
    """Exponential backoff for a 0-indexed retry attempt, capped at ~120s."""
    return min(2.0**attempt, MAX_BACKOFF_SECONDS)


def call_with_retry(
    call_fn: Callable[[], T],
    *,
    sleep_fn: Callable[[float], None] = time.sleep,
    max_429_attempts: int = MAX_429_ATTEMPTS,
    max_5xx_attempts: int = MAX_5XX_ATTEMPTS,
) -> T:
    """Call call_fn(), retrying in place on ProviderCallError:
    - 429: sleeps `retry_after` if the provider sent one, else a capped
      exponential backoff, then retries — up to max_429_attempts times.
    - 5xx: retries up to max_5xx_attempts times (with the same backoff)
      before giving up.
    - anything else: re-raised immediately, not retried here.

    Once retries are exhausted, re-raises the last ProviderCallError — the
    caller (call_with_fallback) treats that as "this provider is done, try
    the next one".
    """
    attempt_429 = 0
    attempt_5xx = 0
    while True:
        try:
            return call_fn()
        except ProviderCallError as exc:
            if exc.status_code == 429:
                if attempt_429 >= max_429_attempts:
                    raise
                delay = exc.retry_after if exc.retry_after is not None else backoff_seconds(attempt_429)
                sleep_fn(min(delay, MAX_BACKOFF_SECONDS))
                attempt_429 += 1
                continue
            if 500 <= exc.status_code < 600:
                if attempt_5xx >= max_5xx_attempts:
                    raise
                sleep_fn(backoff_seconds(attempt_5xx))
                attempt_5xx += 1
                continue
            raise


def call_with_fallback(
    providers: list,
    call_fn_factory: Callable[[object], Callable[[], T]],
    **retry_kwargs,
) -> tuple[T, object]:
    """Try `providers` in order. For each, build a fresh call_fn via
    call_fn_factory(provider) and run it through call_with_retry. Returns
    (result, provider) for the first provider that succeeds.

    Raises AllProvidersFailedError (carrying every provider's error) if the
    whole chain is exhausted.
    """
    errors: dict[str, Exception] = {}
    for provider in providers:
        try:
            result = call_with_retry(call_fn_factory(provider), **retry_kwargs)
            return result, provider
        except ProviderCallError as exc:
            # Only an HTTP-level failure reported via ProviderCallError falls
            # over to the next provider. Anything else (a programming bug in
            # call_fn_factory/call_fn) is a real error and must propagate,
            # not be silently swallowed as "this provider failed".
            errors[provider.name] = exc
    raise AllProvidersFailedError(errors)
