"""Per-call benchmark journal (issue #10).

One entry per provider network attempt — a chat completion, or OpenRouter's
`GET /models` catalog lookup — every in-place 429/5xx retry included, not
just the call that finally succeeds or the one that ends a provider's turn
in the fallback chain (issues #6-#8). Each entry records what issue #10's
acceptance criteria asks for: provider, model, real input/output tokens,
success/failure, error code. Written immediately (append + flush per call),
not buffered, so a run interrupted partway through still leaves a log
usable for the section-2 RPM/RPD/TPM/context comparison the benchmark
exists to produce — summarize() also derives an *observed* req/min and
tokens/min per provider from each entry's timestamp, for a direct
side-by-side against those published limits.

Pure logic only (JSON in, JSON out) beyond the file append itself, so
aggregation/formatting are unit-testable without network access — same
split as quota_state.py and taxonomy_core.py.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Below this, a provider's calls span too little wall-clock time in the log
# for calls/minute or tokens/minute to mean anything (a burst of calls a few
# milliseconds apart would otherwise report an absurd "observed" rate).
MIN_ELAPSED_MINUTES_FOR_RATE = 1.0 / 60.0

DEFAULT_LOG_PATH = Path(__file__).resolve().parent / "benchmark_log.jsonl"

# error_code of an entry that is *not* a network call: tag_chapter rejected an
# envelope the provider returned with HTTP 200 (schema-invalid, or the wrong
# chapter.number) and wrote nothing (issue #12). Logged so the report can
# tell "call OK" from "file written"; summarize() keeps these out of the
# call/failure/rate counts, since the call itself is already logged as a
# success.
VALIDATION_REJECTED = "validation_rejected"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CallLogEntry:
    chapter: int | None
    provider: str
    model: str | None
    success: bool
    input_tokens: int | None = None
    output_tokens: int | None = None
    error_code: int | str | None = None
    error_message: str | None = None
    timestamp: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BenchmarkLog:
    """Appends CallLogEntry rows to a JSONL file at `path`, one line per
    `record()` call. `path=None` keeps everything in `self.entries` only
    (never touches disk) — for tests and callers that don't want a run to
    write API/benchmark_log.jsonl."""

    def __init__(self, path: Path | None = DEFAULT_LOG_PATH):
        self.path = path
        self.entries: list[CallLogEntry] = []
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, entry: CallLogEntry) -> None:
        self.entries.append(entry)
        if self.path is None:
            return
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")


def load_entries(path: Path) -> list[dict[str, Any]]:
    """Read every logged call back from a JSONL file, e.g. to report on a
    previous (possibly interrupted) run without re-running it."""
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def _token_stats(values: list[int]) -> dict[str, float | int | None]:
    if not values:
        return {"min": None, "max": None, "avg": None}
    return {"min": min(values), "max": max(values), "avg": round(sum(values) / len(values), 1)}


def summarize(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per-provider aggregates — call counts, error code breakdown, token
    stats over successful calls, and *observed* calls/minute and
    tokens/minute (from each entry's own timestamp, spanning a provider's
    first to last logged call in this run) — the numbers to compare against
    each provider's published RPM/RPD/TPM/context limits (issue #10 AC:
    "produce a report exploitable for that comparison"). Observed rates are
    None when too few calls or too little elapsed time were logged for a
    rate to be meaningful (a single call, or a burst within the same
    second) — the raw JSONL log still has every timestamp for a manual
    calculation in that case."""
    by_provider: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        by_provider.setdefault(entry["provider"], []).append(entry)

    summary: dict[str, dict[str, Any]] = {}
    for provider, all_entries in by_provider.items():
        rejected = sum(1 for e in all_entries if e.get("error_code") == VALIDATION_REJECTED)
        provider_entries = [e for e in all_entries if e.get("error_code") != VALIDATION_REJECTED]
        successes = [e for e in provider_entries if e.get("success")]
        failures = [e for e in provider_entries if not e.get("success")]
        input_tokens = [e["input_tokens"] for e in successes if e.get("input_tokens") is not None]
        output_tokens = [e["output_tokens"] for e in successes if e.get("output_tokens") is not None]

        error_codes: dict[str, int] = {}
        for entry in failures:
            key = str(entry.get("error_code"))
            error_codes[key] = error_codes.get(key, 0) + 1

        timestamps = sorted(
            datetime.fromisoformat(e["timestamp"]) for e in provider_entries if e.get("timestamp")
        )
        elapsed_minutes = (
            (timestamps[-1] - timestamps[0]).total_seconds() / 60 if len(timestamps) >= 2 else 0.0
        )
        has_meaningful_span = elapsed_minutes >= MIN_ELAPSED_MINUTES_FOR_RATE
        total_tokens = sum(input_tokens) + sum(output_tokens)
        input_stats = _token_stats(input_tokens)
        output_stats = _token_stats(output_tokens)

        summary[provider] = {
            "calls": len(provider_entries),
            "successes": len(successes),
            "failures": len(failures),
            "rejected": rejected,
            # Every successful call either wrote its chapter file or was
            # rejected by validation — chapters skipped as already tagged
            # make no call and so no entry.
            "files_written": len(successes) - rejected,
            "error_codes": error_codes,
            "input_tokens_min": input_stats["min"],
            "input_tokens_max": input_stats["max"],
            "input_tokens_avg": input_stats["avg"],
            "output_tokens_min": output_stats["min"],
            "output_tokens_max": output_stats["max"],
            "output_tokens_avg": output_stats["avg"],
            "elapsed_minutes": round(elapsed_minutes, 3) if has_meaningful_span else None,
            "observed_rpm": round(len(provider_entries) / elapsed_minutes, 2) if has_meaningful_span else None,
            "observed_tpm": round(total_tokens / elapsed_minutes, 1) if has_meaningful_span else None,
        }
    return summary


def format_report(summary: dict[str, dict[str, Any]]) -> str:
    """Human-readable text report, one block per provider."""
    if not summary:
        return "(no calls logged)"
    lines = []
    for provider in sorted(summary):
        s = summary[provider]
        lines.append(f"{provider}:")
        lines.append(f"  calls: {s['calls']} (success: {s['successes']}, failure: {s['failures']})")
        lines.append(f"  files written: {s['files_written']} (rejected by validation: {s['rejected']})")
        if s["error_codes"]:
            codes = ", ".join(f"{code}×{count}" for code, count in sorted(s["error_codes"].items()))
            lines.append(f"  error codes: {codes}")
        lines.append(
            f"  input tokens:  min={s['input_tokens_min']} avg={s['input_tokens_avg']} max={s['input_tokens_max']}"
        )
        lines.append(
            f"  output tokens: min={s['output_tokens_min']} avg={s['output_tokens_avg']} max={s['output_tokens_max']}"
        )
        if s["observed_rpm"] is not None:
            lines.append(f"  observed rate: {s['observed_rpm']} req/min, {s['observed_tpm']} tokens/min "
                         f"(over {s['elapsed_minutes']} min)")
        else:
            lines.append("  observed rate: n/a (not enough elapsed time logged for this provider)")
    return "\n".join(lines)
