#!/usr/bin/env python3
"""
Taxonomy tagging client (issue #5) — single OpenAI-compatible HTTP client,
one chapter (entire silver .md, front-matter + every section) per call.
First provider wired: Gemini, via Google AI Studio's OpenAI-compatible endpoint.

Reads data/silver/chapter_NNNN.md, writes data/taxonomy/chapter_NNNN.json.
Chapters already present under data/taxonomy/ are skipped: no re-call, no
re-consumed quota.

Usage:
    python API/taxonomy_client.py --chapters 1 2
    python API/taxonomy_client.py --max-chapter 50

See API/README.md for how to obtain and set GEMINI_API_KEY.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from providers import PROVIDERS, ProviderConfig  # noqa: E402
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


def call_provider(
    provider: ProviderConfig,
    system_prompt: str,
    chapter_markdown: str,
    json_schema: dict,
) -> dict:
    """One OpenAI-compatible chat completion call with a strict json_schema
    response_format. Not covered by tests: it needs network access."""
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
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return json.loads(content)


def tag_chapter(
    number: int,
    provider: ProviderConfig,
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
    envelope = call_provider(provider, system_prompt, chapter_markdown, json_schema)

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


def run(chapters: list[int] | None, max_chapter: int | None, provider_name: str) -> None:
    load_dotenv(REPO_ROOT / ".env")
    provider = PROVIDERS[provider_name]

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
        tag_chapter(number, provider, system_prompt, json_schema)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--chapters", type=int, nargs="+", help="explicit chapter numbers to tag")
    p.add_argument("--max-chapter", type=int, help="tag chapters 1..N")
    p.add_argument("--provider", default="gemini", choices=sorted(PROVIDERS))
    args = p.parse_args()
    run(args.chapters, args.max_chapter, args.provider)


if __name__ == "__main__":
    main()
