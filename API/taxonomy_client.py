#!/usr/bin/env python3
"""
Taxonomy tagging client (issue #5) — single OpenAI-compatible HTTP client,
one chapter (entire silver .md, front-matter + every section) per call.
Providers are tried in a fallback chain (issues #6, #7, #8): Gemini first,
Mistral as 2nd relay, Groq as 3rd relay, OpenRouter as 4th and last relay
if the prior links error persistently or their quota is exhausted — checked
preventively via a persistent local counter (issue #9,
API/quota_state.json) before a provider is even called.

Reads data/silver/chapter_NNNN.md, writes data/taxonomy/chapter_NNNN.json.
Chapters already present under data/taxonomy/ are skipped: no re-call, no
re-consumed quota.

Usage:
    python API/taxonomy_client.py --chapters 1 2
    python API/taxonomy_client.py --max-chapter 50

See API/README.md for how to obtain and set GEMINI_API_KEY / MISTRAL_API_KEY /
GROQ_API_KEY / OPENROUTER_API_KEY.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_log import VALIDATION_REJECTED, BenchmarkLog, CallLogEntry  # noqa: E402
from fights_index import update_fights_index_file  # noqa: E402
from provider_fallback import AllProvidersFailedError, ProviderCallError, call_with_fallback  # noqa: E402
from providers import FALLBACK_CHAIN, PROVIDERS, ProviderConfig  # noqa: E402
from quota_state import QUOTA_EXHAUSTED_STATUS, QuotaState  # noqa: E402
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


def _raise_for_provider_status(provider: ProviderConfig, response) -> None:
    """Turn any HTTP error into a ProviderCallError, never a bare
    requests.HTTPError: 429/5xx are retried in place by call_with_retry;
    any other 4xx (observed: OpenRouter 404 once a pinned free model left
    its catalog) is re-raised at once there, so it falls over to the next
    provider in a chain and fails just that pair in the benchmark instead
    of crashing the whole run. The body is kept since it says *why*."""
    if response.status_code == 429 or 500 <= response.status_code < 600:
        raise ProviderCallError(response.status_code, retry_after=_parse_retry_after(response))
    if response.status_code >= 400:
        detail = (getattr(response, "text", "") or "")[:300]
        raise ProviderCallError(
            response.status_code,
            message=f"{provider.name}: HTTP {response.status_code} for {getattr(response, 'url', '?')}: {detail}",
        )


def resolve_free_model(provider: ProviderConfig) -> str:
    """Pick a `:free` model id from the provider's live catalog (issue #8) —
    `GET /models?max_price=0` — instead of a hardcoded id, since the free
    catalog rotates over time. Called once per provider attempt (from the
    call_provider_chain factory, not from inside call_provider), so it isn't
    re-run on every in-place 429/5xx retry of the completion call.

    Raises ProviderCallError — on 429/5xx, or when the catalog currently has
    no `:free` model at all — so a resolution failure is folded into the same
    per-provider error (and, if every provider fails, the same
    AllProvidersFailedError) as a chat completion failure, instead of
    escaping as a bare, unhandled exception."""
    url = provider.base_url.rstrip("/") + "/models"
    headers = {
        "Authorization": f"Bearer {provider.api_key()}",
        **(provider.extra_headers or {}),
    }
    try:
        response = requests.get(url, headers=headers, params={"max_price": 0}, timeout=30)
    except requests.exceptions.RequestException as exc:
        # A transport-level failure (timeout, connection reset, ...) never
        # reaches response.status_code — without this it propagates as a
        # bare requests exception, uncaught by call_with_fallback, and
        # crashes the whole run instead of falling over like a 5xx would.
        raise ProviderCallError(503, message=f"{provider.name}: {exc}") from exc
    _raise_for_provider_status(provider, response)
    free_models = [m["id"] for m in response.json().get("data", []) if m.get("id", "").endswith(":free")]
    if not free_models:
        raise ProviderCallError(503, message=f"{provider.name}: no ':free' model available in the current catalog")
    return free_models[0]


def call_provider(
    provider: ProviderConfig,
    model: str,
    system_prompt: str,
    chapter_markdown: str,
    json_schema: dict,
) -> tuple[dict, dict[str, int | None]]:
    """One OpenAI-compatible chat completion call with a strict json_schema
    response_format. Raises ProviderCallError on 429/5xx so
    provider_fallback.call_with_retry can react (retry in place, or give up
    on this provider), and on any other HTTP error (see
    _raise_for_provider_status).
    Not covered by tests: it needs network access.

    Returns (envelope, usage) where `usage` is the real input/output token
    counts from the response's OpenAI-compatible `usage` object (issue #10)
    — `{"input_tokens": None, "output_tokens": None}` if a provider omits
    that object, rather than failing the call over a benchmark-only detail."""
    url = provider.base_url.rstrip("/") + "/chat/completions"
    # Spec section 4.3: strict json_schema only for providers confirmed to
    # support it (ProviderConfig.supports_strict_json_schema); everyone else
    # gets free-form json_object and leans on the applicative schema
    # validation tag_chapter already runs on every response.
    if provider.supports_strict_json_schema:
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "taxonomy_envelope_v1",
                "strict": True,
                "schema": json_schema,
            },
        }
    else:
        response_format = {"type": "json_object"}
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": chapter_markdown},
        ],
        "response_format": response_format,
        # Some providers (observed on Groq) default to a completion budget too
        # small for a chapter with several characters/interactions, and
        # truncate the JSON mid-object instead of erroring — surfaced as a
        # 400 "does not validate: missing properties" rather than a 429/5xx,
        # so it isn't retried or fallen over, it just crashes the run.
        "max_completion_tokens": 8192,
    }
    headers = {
        "Authorization": f"Bearer {provider.api_key()}",
        "Content-Type": "application/json",
        **(provider.extra_headers or {}),
    }
    try:
        response = requests.post(url, headers=headers, json=body, timeout=120)
    except requests.exceptions.RequestException as exc:
        # Same reasoning as resolve_free_model: a transport-level failure
        # (observed here as a Gemini outage manifesting as a hung read that
        # times out rather than a clean 503) must become a ProviderCallError
        # so the run falls over/retries instead of crashing.
        raise ProviderCallError(503, message=f"{provider.name}: {exc}") from exc
    _raise_for_provider_status(provider, response)
    payload = response.json()
    # OpenRouter (see providers.py's OPENROUTER comment) can answer with
    # HTTP 200 but an in-band `{"error": ...}` body instead of `choices`
    # when the upstream free model itself fails (no capacity, moderation,
    # etc.). Surfaced here as a ProviderCallError, same as any other
    # provider failure, instead of a raw KeyError/IndexError that isn't
    # caught by call_with_fallback and crashes the whole run.
    if not payload.get("choices"):
        error = payload.get("error") or {}
        code = error.get("code")
        status_code = code if isinstance(code, int) and 400 <= code < 600 else 502
        raise ProviderCallError(
            status_code,
            message=f"{provider.name}: provider returned no choices: {error.get('message') or payload}",
        )
    choice = payload["choices"][0]
    content = choice.get("message", {}).get("content")
    if not content:
        # `choices` was non-empty but the message content itself is null/empty
        # — observed on reasoning models that put their answer in a separate
        # field and leave `content` null, or a response cut off by
        # finish_reason "length"/"content_filter". Same treatment as a
        # missing `choices`: a ProviderCallError the fallback/benchmark loop
        # can log and move past, not a raw TypeError from json.loads(None).
        raise ProviderCallError(
            502,
            message=f"{provider.name}: empty message content (finish_reason={choice.get('finish_reason')!r})",
        )
    usage = payload.get("usage") or {}
    return json.loads(content), {
        "input_tokens": usage.get("prompt_tokens"),
        "output_tokens": usage.get("completion_tokens"),
    }


def call_provider_chain(
    providers: list[ProviderConfig],
    system_prompt: str,
    chapter_markdown: str,
    json_schema: dict,
    quota: QuotaState | None = None,
    chapter: int | None = None,
    log: BenchmarkLog | None = None,
    before_call: Callable[[ProviderConfig], None] | None = None,
    **retry_kwargs,
) -> tuple[dict, ProviderConfig]:
    """Try `providers` in order (issue #6): current provider first, retrying
    in place on 429/5xx, then falling over to the next provider if it's
    still failing. Returns (envelope, provider_that_succeeded).

    `quota` (issue #9) is checked *before* each provider is attempted: a
    provider whose local daily budget is exhausted (see
    ProviderConfig.daily_limit) is skipped straight away — no network call —
    exactly like a persistently-failing provider falling over to the next
    one. Defaults to an in-memory, never-persisted QuotaState so callers
    that don't care about quotas (e.g. most tests) aren't affected by, or
    don't affect, API/quota_state.json.

    `log` (issue #10), if given, gets one CallLogEntry per network attempt
    made against a provider — a chat completion or, for OpenRouter, the
    `GET /models` catalog lookup — every in-place 429/5xx retry included,
    not just the call that finally succeeds or ends a provider's turn.
    Records provider, model (None if a catalog lookup itself failed, since
    no model was resolved yet), real input/output tokens, and
    success/failure with its error code. A provider skipped outright for
    exhausted quota never reaches the network, so it isn't logged as a
    call. `chapter` is carried on each entry so the log can be
    cross-referenced with data/taxonomy/chapter_NNNN.json.

    `before_call` (issue #12), if given, runs right before every chat
    completion attempt, in-place retries included — run_benchmark.py uses it
    to pace each provider to its `min_interval_s`.

    `retry_kwargs` (e.g. `sleep_fn`, `max_429_attempts`) are forwarded to
    call_with_fallback — tests inject a no-op `sleep_fn` there instead of
    waiting on real backoffs, and the benchmark passes `max_429_attempts=0`
    so a 429 surfaces at once instead of being retried in place."""
    if quota is None:
        quota = QuotaState(path=None)

    def factory(provider: ProviderConfig):
        if not quota.has_budget(provider.quota_name, provider.daily_limit):
            raise ProviderCallError(
                QUOTA_EXHAUSTED_STATUS,
                message=f"{provider.name}: local daily quota exhausted, skipped without a network call",
            )

        def log_attempt(*, model_used, success, **fields):
            if log is not None:
                log.record(
                    CallLogEntry(chapter=chapter, provider=provider.name, model=model_used, success=success, **fields)
                )

        # Resolved once per provider attempt, not on every in-place retry
        # (issue #8) — a resolution failure here is a ProviderCallError,
        # caught by call_with_fallback exactly like a completion failure.
        try:
            model = provider.model() or resolve_free_model(provider)
        except ProviderCallError as exc:
            log_attempt(model_used=None, success=False, error_code=exc.status_code, error_message=str(exc))
            raise

        def attempt():
            if before_call is not None:
                before_call(provider)
            try:
                envelope, usage = call_provider(provider, model, system_prompt, chapter_markdown, json_schema)
            except ProviderCallError as exc:
                log_attempt(model_used=model, success=False, error_code=exc.status_code, error_message=str(exc))
                raise
            log_attempt(
                model_used=model,
                success=True,
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
            )
            return envelope

        return attempt

    envelope, used_provider = call_with_fallback(providers, factory, **retry_kwargs)
    quota.record_success(used_provider.quota_name)
    return envelope, used_provider


def tag_chapter(
    number: int,
    providers: list[ProviderConfig],
    system_prompt: str,
    json_schema: dict,
    quota: QuotaState | None = None,
    log: BenchmarkLog | None = None,
    output_dir: Path | None = None,
    **chain_kwargs,
) -> Path | None:
    """`output_dir` (default: TAXONOMY_DIR, i.e. `data/taxonomy/`) is where
    `chapter_NNNN.json` and this run's `fights_index.json` are written and
    where the "already tagged, skip" resumability check looks. The benchmark
    (run_benchmark.py) passes one subdirectory per model — e.g.
    `data/taxonomy/gemini/` — since its whole point is comparing each
    model's own tagging output on the same chapters side by side, not just
    whichever provider a production fallback chain happened to answer with
    first (issue #3 spec section 1: "pour chaque provider/modèle... envoyer
    un appel par chapitre"). Resolved from the module-level TAXONOMY_DIR at
    call time (not bound as a mutable default) so tests patching
    `taxonomy_client.TAXONOMY_DIR` keep working unchanged.

    `chain_kwargs` (e.g. `before_call`, `max_429_attempts`, `sleep_fn`) are
    forwarded to call_provider_chain.

    A rejected envelope (ValueError below) is also journaled to `log` as a
    VALIDATION_REJECTED entry (issue #12): the call itself was logged as a
    success, but no file was written."""
    if output_dir is None:
        output_dir = TAXONOMY_DIR

    silver_path = SILVER_DIR / f"chapter_{number:04d}.md"
    if not silver_path.exists():
        print(f"chapter {number}: no silver file at {silver_path}, skipped")
        return None

    already = output_dir / f"chapter_{number:04d}.json"
    if already.exists():
        print(f"chapter {number}: {already} already exists, skipped (no API call)")
        return None

    chapter_markdown = silver_path.read_text(encoding="utf-8")
    try:
        envelope, used_provider = call_provider_chain(
            providers, system_prompt, chapter_markdown, json_schema, quota=quota, chapter=number, log=log,
            **chain_kwargs,
        )
    except AllProvidersFailedError as exc:
        # issue #8 AC: never silently skip a chapter when every provider in
        # the chain is exhausted — surface it loudly and re-raise instead of
        # letting the batch loop move on unnoticed.
        print(
            f"chapter {number}: ALL PROVIDERS FAILED ({', '.join(p.name for p in providers)}): {exc}",
            file=sys.stderr,
        )
        raise
    if used_provider is not providers[0]:
        print(f"chapter {number}: fell back to provider '{used_provider.name}'")

    def reject(message: str) -> ValueError:
        if log is not None:
            log.record(CallLogEntry(
                chapter=number, provider=used_provider.name, model=used_provider.model(),
                success=False, error_code=VALIDATION_REJECTED, error_message=message,
            ))
        return ValueError(message)

    errors = validate_taxonomy_envelope(envelope, json_schema)
    if errors:
        raise reject(
            f"chapter {number}: model output failed schema validation:\n" + "\n".join(errors)
        )

    # A model can return a schema-valid envelope that just isn't about the
    # chapter it was asked for (observed on Groq: asked for chapter 1's
    # silver .md, it returned a well-formed chapter 82 envelope, apparently
    # drawn from parametric memory instead of the supplied text). Trusting
    # chapter.number blindly here would write chapter_0082.json for a
    # request that was never made, silently colliding with (or shadowing)
    # this run's real chapter 82 later — so it's rejected the same way as a
    # schema error, not written to disk.
    returned_number = envelope.get("chapter", {}).get("number")
    if returned_number != number:
        raise reject(
            f"chapter {number}: model output claims to be chapter.number="
            f"{returned_number!r} instead of the requested {number} — rejected, not written"
        )

    filename = taxonomy_output_filename(envelope)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / filename
    out_path.write_text(json.dumps(envelope, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"chapter {number}: wrote {out_path}")

    # issue #11: keep the Fights Index in sync as soon as a chapter with at
    # least one `type: fight` interaction is written — a no-op otherwise, so
    # a chapter with no fight never creates/touches fights_index.json. Kept
    # under the same output_dir as the chapter file: each model's fallback
    # chain produces its own fight_id continuity, so a per-model benchmark
    # run gets its own fights_index.json, never a shared/mixed one.
    if any(i.get("type") == "fight" for i in envelope.get("interactions", [])):
        update_fights_index_file(number, envelope, path=output_dir / "fights_index.json")

    return out_path


def run(chapters: list[int] | None, max_chapter: int | None, provider_names: list[str]) -> None:
    load_dotenv(REPO_ROOT / ".env")
    providers = [PROVIDERS[name] for name in provider_names]
    # Loaded once and shared across every chapter in this run (issue #9): a
    # provider's budget spent tagging chapter N carries over to chapter N+1
    # in the same run, and persists to API/quota_state.json so it also
    # carries over across a cold restart of the script.
    quota = QuotaState()

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
        try:
            tag_chapter(number, providers, system_prompt, json_schema, quota=quota)
        except AllProvidersFailedError:
            # Already printed loudly by tag_chapter (issue #8 AC) — move on
            # to the next chapter instead of losing the rest of a
            # potentially long (up to 1193-chapter) run over one exhausted
            # chapter; it stays absent from data/taxonomy/, so a later rerun
            # picks it back up.
            continue
        except ValueError as exc:
            # A schema-invalid envelope, or one whose self-reported
            # chapter.number doesn't match what was requested (a model
            # hallucinating an unrelated chapter instead of grounding in the
            # supplied text) — rejected by tag_chapter before being written.
            # Same reasoning as above: log loudly and keep going.
            print(f"chapter {number}: rejected model output: {exc}", file=sys.stderr)
            continue


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
