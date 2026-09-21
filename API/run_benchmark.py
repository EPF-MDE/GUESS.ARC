#!/usr/bin/env python3
"""Benchmark run + per-call journal (issue #10).

Runs the full Gemini -> Mistral -> Groq -> OpenRouter fallback chain (with
the local quota counter, issue #9) over a configurable batch of chapters
(default: the first 20) drawn from data/silver/, tagging each one exactly
like taxonomy_client.py does. Every provider call attempt is journaled to a
JSONL log (API/benchmark_log.py) — provider/model, real input/output
tokens, success/failure, error code — and a per-provider summary report is
printed at the end, to compare against each provider's published
RPM/RPD/TPM/context limits (spec section 2) and decide which model(s) scale
to the full 1193-chapter corpus.

Resumable: reuses taxonomy_client.tag_chapter's existing skip-if-already-
tagged logic (issue #5) — chapters already present under data/taxonomy/ are
not re-sent, so re-running the same batch after an interruption costs no
extra API calls or quota for chapters it already finished.

Usage:
    python API/run_benchmark.py
    python API/run_benchmark.py --batch-size 50
    python API/run_benchmark.py --chapters 1 2 3
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
from taxonomy_client import SCHEMA_DOC_PATH, SILVER_DIR, load_json_schema, tag_chapter  # noqa: E402
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
    providers = [PROVIDERS[name] for name in provider_names]
    quota = QuotaState()
    log = BenchmarkLog(path=log_path)

    taxonomy_definition = extract_taxonomy_definition(SCHEMA_DOC_PATH.read_text(encoding="utf-8"))
    system_prompt = build_system_prompt(taxonomy_definition)
    json_schema = load_json_schema()

    numbers = sorted(chapters) if chapters else default_batch(batch_size)
    if not numbers:
        raise SystemExit(f"no chapter_NNNN.md files found under {SILVER_DIR}")

    print(f"benchmark run: {len(numbers)} chapter(s) {numbers[0]}..{numbers[-1]}, "
          f"providers={provider_names}, log={log.path}")

    failed_chapters = []
    for number in numbers:
        try:
            tag_chapter(number, providers, system_prompt, json_schema, quota=quota, log=log)
        except AllProvidersFailedError:
            # Already printed loudly by tag_chapter (issue #8 AC) — keep the
            # batch going so one exhausted chapter doesn't block the rest of
            # the run, but remember it to report a non-zero exit at the end.
            failed_chapters.append(number)

    if log.path is not None:
        print_report(log.path)

    if failed_chapters:
        print(
            f"\n{len(failed_chapters)} chapter(s) failed on every provider: {failed_chapters}",
            file=sys.stderr,
        )
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
        help="ordered fallback chain, current provider first (default: %(default)s)",
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
