#!/usr/bin/env python3
"""Benchmark run + per-call journal (issue #10).

Spec section 1: the point of this benchmark is to compare providers against
each other on the *same* batch of chapters — "pour chaque provider/modèle
de la section 2, envoyer un appel par chapitre". So each provider in
`--providers` (default: all 4, gemini/mistral/groq/openrouter) is called
independently on every chapter of the batch: no cross-provider fallback
here (a provider that fails on a chapter is just logged as a failure for
that model, retried in place on 429/5xx same as always, but the run moves
on to the next chapter for that same provider — it never hands the chapter
to a different model). That is deliberately different from
taxonomy_client.py's default CLI, which chains providers as a reliability
fallback (first success wins) for tagging the real corpus once a model has
been picked from this benchmark's results.

Each provider writes its own chapter_NNNN.json under
data/taxonomy/<provider>/ (never a shared data/taxonomy/chapter_NNNN.json)
so the 4 models' outputs on the same chapters stay side by side and can be
diffed/compared — not just their aggregate stats. Every provider call
attempt is still journaled to one JSONL log (API/benchmark_log.py) —
provider/model, real input/output tokens, success/failure, error code — and
a per-provider summary report is printed at the end, to compare against
each provider's published RPM/RPD/TPM/context limits (spec section 2) and
decide which model(s) scale to the full 1193-chapter corpus.

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
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_log import BenchmarkLog, DEFAULT_LOG_PATH, format_report, load_entries, summarize  # noqa: E402
from provider_fallback import AllProvidersFailedError  # noqa: E402
from providers import FALLBACK_CHAIN, PROVIDERS  # noqa: E402
from quota_state import QuotaState  # noqa: E402
from taxonomy_client import SCHEMA_DOC_PATH, SILVER_DIR, TAXONOMY_DIR, load_json_schema, tag_chapter  # noqa: E402
from taxonomy_core import build_system_prompt, extract_taxonomy_definition  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
CHAPTER_NUMBER_RE = re.compile(r"chapter_(\d+)\.md$")


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

    numbers = sorted(chapters) if chapters else default_batch(batch_size)
    if not numbers:
        raise SystemExit(f"no chapter_NNNN.md files found under {SILVER_DIR}")

    print(f"benchmark run: {len(numbers)} chapter(s) {numbers[0]}..{numbers[-1]}, "
          f"providers={provider_names} (each called independently, no cross-provider "
          f"fallback — see module docstring), log={log.path}")

    # One model at a time, retried in place on 429/5xx (no fallover to the
    # next provider — see module docstring): the goal is per-model results
    # on the identical chapter batch, not "whichever model answered first".
    failed: list[tuple[str, int]] = []
    for name in provider_names:
        provider = PROVIDERS[name]
        output_dir = TAXONOMY_DIR / provider.name
        for number in numbers:
            try:
                tag_chapter(
                    number, [provider], system_prompt, json_schema,
                    quota=quota, log=log, output_dir=output_dir,
                )
            except AllProvidersFailedError:
                # Already printed loudly by tag_chapter (issue #8 AC) — keep
                # the batch going so one exhausted (provider, chapter) pair
                # doesn't block the rest of the run, but remember it to
                # report a non-zero exit at the end.
                failed.append((name, number))

    if log.path is not None:
        print_report(log.path)

    if failed:
        by_provider: dict[str, list[int]] = {}
        for name, number in failed:
            by_provider.setdefault(name, []).append(number)
        detail = "; ".join(f"{name}: {nums}" for name, nums in by_provider.items())
        print(f"\n{len(failed)} (provider, chapter) pair(s) failed: {detail}", file=sys.stderr)
        raise SystemExit(1)


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
