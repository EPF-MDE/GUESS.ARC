#!/usr/bin/env python3
"""Benchmark run + per-call journal (issue #10).

Spec section 1: the point of this benchmark is to compare providers against
each other on the *same* batch of chapters — "pour chaque provider/modèle
de la section 2, envoyer un appel par chapitre". So each provider in
`--providers` (default: all 6 — gemini/mistral/groq plus the 3 fixed
OpenRouter models, openrouter-nemotron/openrouter-nex-pro/openrouter-dots)
is called independently on every chapter of the batch: no cross-provider fallback
here (a provider that fails on a chapter is just logged as a failure for
that model — it never hands the chapter to a different model). That is
deliberately different from
taxonomy_client.py's default CLI, which chains providers as a reliability
fallback (first success wins) for tagging the real corpus once a model has
been picked from this benchmark's results.

Each provider writes its own chapter_NNNN.json under
data/taxonomy/<provider>/ (never a shared data/taxonomy/chapter_NNNN.json)
so each model's outputs on the same chapters stay side by side and can be
diffed/compared — not just their aggregate stats. Every provider call
attempt is still journaled to one JSONL log (API/benchmark_log.py) —
provider/model, real input/output tokens, success/failure, error code — and
a per-provider summary report is printed at the end, to compare against
each provider's published RPM/RPD/TPM/context limits (spec section 2) and
decide which model(s) scale to the full 1193-chapter corpus.

Quota-frugal on free tiers (issue #12, see run_batch): chapters are sent
round-robin across providers, each provider paced to its
ProviderConfig.min_interval_s, a 429 is deferred to the end of the batch
instead of retried in place, and a repeated 429 marks the provider exhausted
for the day in API/quota_state.json — a same-day rerun skips it without any
network call. 5xx keep tag_chapter's short in-place retry.

Resumable per provider: reuses taxonomy_client.tag_chapter's existing
skip-if-already-tagged logic (issue #5), scoped to each provider's own
data/taxonomy/<provider>/ directory — chapters a given model already tagged
are not re-sent to it, so re-running the same batch after an interruption
costs no extra API calls or quota for the (provider, chapter) pairs already
done, independently per provider.

Usage:
    python API/run_benchmark.py
    python API/run_benchmark.py --batch-size 50
    python API/run_benchmark.py --chapters 1 2 3
    python API/run_benchmark.py --providers gemini mistral   # subset of models to compare
    python API/run_benchmark.py --report-only   # summarize a previous run's log, no calls

See API/README.md for how to obtain and set GEMINI_API_KEY / MISTRAL_API_KEY /
GROQ_API_KEY / OPENROUTER_API_KEY.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_log import BenchmarkLog, DEFAULT_LOG_PATH, format_report, load_entries, summarize  # noqa: E402
from provider_fallback import AllProvidersFailedError  # noqa: E402
from providers import FALLBACK_CHAIN, PROVIDERS, ProviderConfig  # noqa: E402
from quota_state import QUOTA_EXHAUSTED_STATUS, QuotaState  # noqa: E402
from taxonomy_client import SCHEMA_DOC_PATH, SILVER_DIR, TAXONOMY_DIR, load_json_schema, tag_chapter  # noqa: E402
from taxonomy_core import build_system_prompt, extract_taxonomy_definition  # noqa: E402
from throttle import Throttle  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
CHAPTER_NUMBER_RE = re.compile(r"chapter_(\d+)\.md$")

# A 429 whose Retry-After exceeds this is a daily quota, not a per-minute
# one: waiting until the end of the batch won't help, so the provider is
# marked exhausted straight away instead of deferred (issue #12).
MAX_DEFERRABLE_RETRY_AFTER_S = 60.0


def default_batch(batch_size: int) -> list[int]:
    """The first `batch_size` chapter numbers available under data/silver/,
    in ascending order (issue #10 AC: configurable batch, default 20, drawn
    from data/silver/ — not assumed to start at chapter 1 or be gap-free)."""
    numbers = sorted(
        int(match.group(1))
        for path in SILVER_DIR.glob("chapter_*.md")
        if (match := CHAPTER_NUMBER_RE.search(path.name))
    )
    return numbers[:batch_size]


def print_report(log_path: Path) -> None:
    entries = load_entries(log_path)
    print(f"\n--- benchmark report ({log_path}, {len(entries)} call(s) logged) ---")
    print(format_report(summarize(entries)))


def run(chapters: list[int] | None, batch_size: int, provider_names: list[str], log_path: Path | None) -> None:
    load_dotenv(REPO_ROOT / ".env")
    quota = QuotaState()
    log = BenchmarkLog(path=log_path)

    taxonomy_definition = extract_taxonomy_definition(SCHEMA_DOC_PATH.read_text(encoding="utf-8"))
    system_prompt = build_system_prompt(taxonomy_definition)
    json_schema = load_json_schema()

    # Fail before any API call, not mid-run once the round-robin reaches a
    # provider whose key or model id is missing from the .env.
    missing = []
    for name in provider_names:
        try:
            PROVIDERS[name].api_key()
            PROVIDERS[name].model()
        except RuntimeError as exc:
            missing.append(f"  {name}: {exc}")
    if missing:
        raise SystemExit("missing configuration, nothing sent:\n" + "\n".join(missing))

    numbers = sorted(chapters) if chapters else default_batch(batch_size)
    if not numbers:
        raise SystemExit(f"no chapter_NNNN.md files found under {SILVER_DIR}")

    print(f"benchmark run: {len(numbers)} chapter(s) {numbers[0]}..{numbers[-1]}, "
          f"providers={provider_names} (each called independently, no cross-provider "
          f"fallback — see module docstring), log={log.path}")

    throttle = Throttle()

    def pace(provider: ProviderConfig) -> None:
        throttle.wait(provider.quota_name, provider.min_interval_s)

    def tag(name: str, number: int) -> None:
        provider = PROVIDERS[name]
        tag_chapter(
            number, [provider], system_prompt, json_schema,
            quota=quota, log=log, output_dir=TAXONOMY_DIR / provider.name,
            before_call=pace, max_429_attempts=0,
        )

    result = run_batch(numbers, provider_names, tag, quota)

    if log.path is not None:
        print_report(log.path)

    for label, pairs in (("failed", result.failed), ("skipped (provider exhausted today)", result.skipped)):
        if pairs:
            print(f"\n{len(pairs)} (provider, chapter) pair(s) {label}: {_by_provider(pairs)}", file=sys.stderr)
    if result.failed or result.skipped:
        raise SystemExit(1)


def _by_provider(pairs: list[tuple[str, int]]) -> str:
    grouped: dict[str, list[int]] = {}
    for name, number in pairs:
        grouped.setdefault(name, []).append(number)
    return "; ".join(f"{name}: {nums}" for name, nums in grouped.items())


@dataclass
class BatchResult:
    failed: list[tuple[str, int]] = field(default_factory=list)
    # Pairs never sent because their provider was out of quota for the day.
    skipped: list[tuple[str, int]] = field(default_factory=list)
    # quota_name keys (not provider names) out of budget for today.
    exhausted: set[str] = field(default_factory=set)


def run_batch(
    numbers: list[int],
    provider_names: list[str],
    tag_fn: Callable[[str, int], object],
    quota: QuotaState,
) -> BatchResult:
    """Quota-frugal schedule for the benchmark (issue #12), independent of
    HTTP: `tag_fn(provider_name, chapter)` does one (provider, chapter) pair
    and raises what tag_chapter raises.

    - Round-robin: chapter N goes to every provider before chapter N+1 goes
      to any, so each provider rests while the others work.
    - A 429 is never retried in place (`tag_fn` must not either): the pair is
      deferred and retried once after the whole batch. A second 429 there —
      or a Retry-After longer than MAX_DEFERRABLE_RETRY_AFTER_S at any
      point — marks the provider exhausted for the day in `quota` (persisted)
      and skips every pair it still had, with no network call. Providers
      already marked exhausted today are skipped from the start. Exhaustion
      is tracked per ProviderConfig.quota_name, the account the quota
      belongs to: the 3 OpenRouter models share one key, so one of them
      proving it spent skips the other two as well.
    - A provider whose local daily budget runs out (QUOTA_EXHAUSTED_STATUS)
      is skipped for the rest of the run too, without a mark: the local
      counter already persists that.
    - Anything else (5xx after tag_chapter's own short retry, a validation
      rejection) fails just that pair; the run goes on."""
    result = BatchResult()
    for key in {PROVIDERS[name].quota_name for name in provider_names}:
        if quota.is_exhausted(key):
            print(f"{key}: marked exhausted earlier today in quota_state.json, skipped (no API call)")
            result.exhausted.add(key)
    deferred: list[tuple[str, int]] = []

    def attempt(name: str, number: int, is_retry: bool) -> None:
        key = PROVIDERS[name].quota_name
        if key in result.exhausted:
            result.skipped.append((name, number))
            return
        try:
            tag_fn(name, number)
        except AllProvidersFailedError as exc:
            # Already printed loudly by tag_chapter (issue #8 AC).
            error = exc.errors.get(name)
            status = getattr(error, "status_code", None)
            if status == QUOTA_EXHAUSTED_STATUS:
                result.exhausted.add(key)
                result.skipped.append((name, number))
            elif status == 429:
                retry_after = error.retry_after
                if is_retry or (retry_after is not None and retry_after > MAX_DEFERRABLE_RETRY_AFTER_S):
                    print(f"{name}: 429 again, '{key}' marked exhausted for today — remaining chapters "
                          f"of every provider on it are skipped", file=sys.stderr)
                    quota.mark_exhausted(key)
                    result.exhausted.add(key)
                    result.failed.append((name, number))
                else:
                    print(f"chapter {number}: {name} answered 429, deferred to the end of the batch")
                    deferred.append((name, number))
            else:
                result.failed.append((name, number))
        except ValueError as exc:
            # tag_chapter rejects a schema-invalid envelope, or one whose
            # self-reported chapter.number doesn't match what was asked for
            # (observed on Groq), instead of writing bad data to disk — and
            # journals it as VALIDATION_REJECTED. One misbehaving pair must
            # not crash the whole benchmark.
            print(f"chapter {number}: rejected {name}'s output: {exc}", file=sys.stderr)
            result.failed.append((name, number))

    for number in numbers:
        for name in provider_names:
            attempt(name, number, is_retry=False)
    for name, number in deferred:
        attempt(name, number, is_retry=True)
    return result


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--batch-size", type=int, default=20,
        help="number of chapters to tag, taken from data/silver/ in ascending order (default: 20)",
    )
    p.add_argument("--chapters", type=int, nargs="+", help="explicit chapter numbers instead of the default batch")
    p.add_argument(
        "--providers", nargs="+", default=FALLBACK_CHAIN, choices=sorted(PROVIDERS),
        help="models to benchmark independently (no cross-provider fallback here — "
             "each writes to its own data/taxonomy/<provider>/) (default: %(default)s)",
    )
    p.add_argument(
        "--log-file", type=Path, default=DEFAULT_LOG_PATH,
        help="JSONL journal path, appended to (default: %(default)s)",
    )
    p.add_argument(
        "--report-only", action="store_true",
        help="print the summary report for --log-file's existing content and exit; makes no API calls",
    )
    args = p.parse_args()

    if args.report_only:
        print_report(args.log_file)
        return

    run(args.chapters, args.batch_size, args.providers, args.log_file)


if __name__ == "__main__":
    main()
