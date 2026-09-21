"""Persistent daily quota counter (issue #9).

Tracks successful calls per provider in `API/quota_state.json`, checked
*before* a provider is called so the fallback chain can move on to the next
link when the local daily budget is exhausted — instead of finding out via a
429. Needed for Groq (its response headers don't expose remaining RPD) and
OpenRouter (hard-capped at 50 requests/day without purchased credits, issue
#9) — see `providers.ProviderConfig.daily_limit`.

Persists across process restarts (the whole point of a *daily* counter) and
only resets the count for a provider whose stored date isn't today's — it is
never reset just because the process restarted.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_STATE_PATH = Path(__file__).resolve().parent / "quota_state.json"

# Sentinel ProviderCallError.status_code for a provider skipped because its
# local quota is exhausted. Deliberately not 429/5xx: provider_fallback's
# call_with_retry only retries in place on those two, so a quota-exhausted
# skip falls straight over to the next provider in the chain, with no
# network call and no retry/backoff.
QUOTA_EXHAUSTED_STATUS = -1


def _today() -> str:
    # UTC calendar day — an approximation of each provider's real reset
    # window (not published by Groq/OpenRouter), consistent with the rest
    # of this module being a best-effort local heuristic, not a mirror of
    # provider-side accounting.
    return datetime.now(timezone.utc).date().isoformat()


class QuotaState:
    """In-memory view of the quota state, backed by a JSON file at `path`:
    `{provider_name: {"date": "YYYY-MM-DD", "count": int}}`.

    `path=None` makes the state purely in-memory (never read from or written
    to disk) — used as the default when no explicit quota tracking is
    wanted, e.g. in tests that don't exercise quota behaviour."""

    def __init__(self, path: Path | None = DEFAULT_STATE_PATH):
        self.path = path
        self._data: dict = self._load()

    def _load(self) -> dict:
        if self.path is None or not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self) -> None:
        if self.path is None:
            return
        self.path.write_text(json.dumps(self._data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def remaining(self, provider_name: str, daily_limit: int | None) -> int | None:
        """Requests left today for `provider_name`, or None if `daily_limit`
        is None (not locally tracked — always considered to have budget)."""
        if daily_limit is None:
            return None
        entry = self._data.get(provider_name)
        if entry is None or entry.get("date") != _today():
            return daily_limit
        return max(daily_limit - int(entry.get("count", 0)), 0)

    def has_budget(self, provider_name: str, daily_limit: int | None) -> bool:
        remaining = self.remaining(provider_name, daily_limit)
        return remaining is None or remaining > 0

    def record_success(self, provider_name: str) -> None:
        """Increment `provider_name`'s count for today (resetting first if
        the stored date isn't today) and persist to disk immediately.

        Only successful calls are counted (issue #9 AC) — an in-place
        429/5xx retry on the same provider (provider_fallback.py) still
        consumes real request budget but isn't reflected here. Harmless: the
        preventive check is a best-effort optimisation, not a hard
        guarantee, and a stale "has budget" reading still safely falls back
        to a real 429/5xx and the normal retry/fallback path."""
        today = _today()
        entry = self._data.get(provider_name)
        if entry is None or entry.get("date") != today:
            entry = {"date": today, "count": 0}
        entry["count"] += 1
        self._data[provider_name] = entry
        self._save()
