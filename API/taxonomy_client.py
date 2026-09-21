#!/usr/bin/env python3
"""
Taxonomy tagging client (issue #5) — single OpenAI-compatible HTTP client,
one chapter (entire silver .md, front-matter + every section) per call.
Providers are tried in a fallback chain (issue #6): Gemini first, Mistral as
2nd relay if Gemini errors persistently or its quota is exhausted.

Reads data/silver/chapter_NNNN.md, writes data/taxonomy/chapter_NNNN.json.
Chapters already present under data/taxonomy/ are skipped: no re-call, no
re-consumed quota.

Usage:
    python API/taxonomy_client.py --chapters 1 2
    python API/taxonomy_client.py --max-chapter 50

See API/README.md for how to obtain and set GEMINI_API_KEY / MISTRAL_API_KEY.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from provider_fallback import ProviderCallError, call_with_fallback  # noqa: E402
from providers import FALLBACK_CHAIN, PROVIDERS, ProviderConfig  # noqa: E402
from taxonomy_core import (  # noqa: E402
    build_system_prompt,
    extract_taxonomy_definition,
    taxonomy_output_filename,
    validate_taxonomy_envelope,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SILVER_DIR = REPO_ROOT / "data" / "silver"
TAXONOMY_DIR = REPO_ROOT / "data" / "taxonomy"
SCHEMA_DOC_PATH = REPO_ROOT / "docs" / "taxonomy-schema.md"
JSON_SCHEMA_PATH = REPO_ROOT / "docs" / "taxonomy-schema.json"


def load_json_schema(path: Path = JSON_SCHEMA_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_retry_after(response: requests.Response) -> float | None:
    """Retry-After in seconds, if the header is present and numeric. The
    HTTP-date form is not handled — falls back to backoff in that case."""
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def call_provider(
    provider: ProviderConfig,
    system_prompt: str,
    chapter_markdown: str,
    json_schema: dict,
) -> dict:
    """One OpenAI-compatible chat completion call with a strict json_schema
    response_format. Raises ProviderCallError on 429/5xx so
    provider_fallback.call_with_retry can react (retry in place, or give up
    on this provider); any other HTTP error propagates via raise_for_status.
    Not covered by tests: it needs network access."""
    url = provider.base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": provider.model(),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": chapter_markdown},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "taxonomy_envelope_v1",
                "strict": True,
                "schema": json_schema,
            },
        },
    }
    headers = {
        "Authorization": f"Bearer {provider.api_key()}",
        "Content-Type": "application/json",
    }
    response = requests.post(url, headers=headers, json=body, timeout=120)
    if response.status_code == 429 or 500 <= response.status_code < 600:
        raise ProviderCallError(response.status_code, retry_after=_parse_retry_after(response))
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return json.loads(content)


def call_provider_chain(
    providers: list[ProviderConfig],
    system_prompt: str,
    chapter_markdown: str,
    json_schema: dict,
    **retry_kwargs,
) -> tuple[dict, ProviderConfig]:
    """Try `providers` in order (issue #6): current provider first, retrying
    in place on 429/5xx, then falling over to the next provider if it's
    still failing. Returns (envelope, provider_that_succeeded).

    `retry_kwargs` (e.g. `sleep_fn`) are forwarded to call_with_fallback —
    tests inject a no-op `sleep_fn` there instead of waiting on real backoffs."""

    def factory(provider: ProviderConfig):
        return lambda: call_provider(provider, system_prompt, chapter_markdown, json_schema)

    return call_with_fallback(providers, factory, **retry_kwargs)


def tag_chapter(
    number: int,
    providers: list[ProviderConfig],
    system_prompt: str,
    json_schema: dict,
) -> Path | None:
    silver_path = SILVER_DIR / f"chapter_{number:04d}.md"
    if not silver_path.exists():
        print(f"chapter {number}: no silver file at {silver_path}, skipped")
        return None

    already = TAXONOMY_DIR / f"chapter_{number:04d}.json"
    if already.exists():
        print(f"chapter {number}: {already} already exists, skipped (no API call)")
        return None

    chapter_markdown = silver_path.read_text(encoding="utf-8")
    envelope, used_provider = call_provider_chain(providers, system_prompt, chapter_markdown, json_schema)
    if used_provider is not providers[0]:
        print(f"chapter {number}: fell back to provider '{used_provider.name}'")

    errors = validate_taxonomy_envelope(envelope, json_schema)
    if errors:
        raise ValueError(
            f"chapter {number}: model output failed schema validation:\n" + "\n".join(errors)
        )

    filename = taxonomy_output_filename(envelope)
    TAXONOMY_DIR.mkdir(parents=True, exist_ok=True)
    out_path = TAXONOMY_DIR / filename
    out_path.write_text(json.dumps(envelope, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"chapter {number}: wrote {out_path}")
    return out_path


def run(chapters: list[int] | None, max_chapter: int | None, provider_names: list[str]) -> None:
    load_dotenv(REPO_ROOT / ".env")
    providers = [PROVIDERS[name] for name in provider_names]

    taxonomy_definition = extract_taxonomy_definition(SCHEMA_DOC_PATH.read_text(encoding="utf-8"))
    system_prompt = build_system_prompt(taxonomy_definition)
    json_schema = load_json_schema()

    if chapters:
        numbers = sorted(chapters)
    elif max_chapter:
        numbers = list(range(1, max_chapter + 1))
    else:
        raise SystemExit("either --chapters or --max-chapter is required")

    for number in numbers:
        tag_chapter(number, providers, system_prompt, json_schema)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--chapters", type=int, nargs="+", help="explicit chapter numbers to tag")
    p.add_argument("--max-chapter", type=int, help="tag chapters 1..N")
    p.add_argument(
        "--providers",
        nargs="+",
        default=FALLBACK_CHAIN,
        choices=sorted(PROVIDERS),
        help="ordered fallback chain, current provider first (default: %(default)s)",
    )
    args = p.parse_args()
    run(args.chapters, args.max_chapter, args.providers)


if __name__ == "__main__":
    main()
