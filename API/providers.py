"""OpenAI-compatible provider configs (issue #5).

A provider is only a base URL, the name of the env var holding its API key, and
a model id — never per-provider request/parsing logic. New providers (ticket
#6+) are added as a new ProviderConfig entry here, not as new client code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    api_key_env: str
    model_env: str
    # True only for a config with no fixed model that picks a `:free` one
    # from the live catalog at call time (issue #8: OpenRouter's free catalog
    # rotates). Every other provider's model comes from `model_env` alone —
    # model ids are configuration, kept in the root .env, never in code.
    resolve_model_from_catalog: bool = False
    # Static headers to send with every request to this provider (issue #8:
    # OpenRouter's HTTP-Referer/X-Title). None for providers that need none.
    extra_headers: dict[str, str] | None = None
    # Local daily request budget enforced by quota_state.py (issue #9). None
    # means "not locally tracked" — Gemini/Mistral expose their remaining RPD
    # in response headers, so a local counter isn't needed for them (yet).
    daily_limit: int | None = None
    # Key quota_state.py counts against (defaults to `name` when None). Set
    # this to a shared value when several ProviderConfigs draw from the same
    # underlying account limit — e.g. multiple fixed OpenRouter models each
    # billed against the same 50 req/day free-tier cap on one API key: they
    # must not each get their own 50, or the local tracker would let the run
    # make 3x the real budget before OpenRouter itself starts 429ing.
    quota_key: str | None = None
    # response_format capability (spec section 4.3): only providers confirmed
    # to support `{"type": "json_schema", "strict": true, ...}` get it: every
    # other provider falls back to `{"type": "json_object"}` and relies on
    # the applicative schema validation already run in tag_chapter on every
    # response regardless of provider. A config flag, not a branch on
    # provider.name, so the fallback/call logic stays generic.
    supports_strict_json_schema: bool = False
    # Minimum seconds between two calls to this provider in the benchmark
    # (issue #12), enforced by throttle.Throttle (run_benchmark.py) before every
    # attempt, keyed by `quota_name` so configs sharing one account share
    # one pace. Derived from each free tier's published limits (see
    # API/README.md): pacing to them is cheaper than learning them via 429s.
    min_interval_s: float = 0.0

    def api_key(self) -> str:
        key = os.environ.get(self.api_key_env)
        if not key:
            raise RuntimeError(
                f"{self.api_key_env} is not set — see API/README.md, "
                f"then set it in the root .env"
            )
        return key

    def model(self) -> str | None:
        """The model id from `model_env`. None only for a catalog-resolved
        config left unset (the caller then resolves one); otherwise a missing
        value is a configuration error, same as a missing API key."""
        value = os.environ.get(self.model_env)
        if value or self.resolve_model_from_catalog:
            return value or None
        raise RuntimeError(
            f"{self.model_env} is not set — see API/README.md, "
            f"then set it in the root .env"
        )

    @property
    def quota_name(self) -> str:
        return self.quota_key or self.name


GEMINI = ProviderConfig(
    name="gemini",
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    api_key_env="GEMINI_API_KEY",
    model_env="GEMINI_MODEL",
    # Confirmed by the spec (section 4.3) as supporting strict json_schema;
    # Mistral/Groq/OpenRouter are not confirmed, so they use json_object.
    supports_strict_json_schema=True,
    # ~20 RPD on the free tier, RPM unpublished.
    min_interval_s=15.0,
)

MISTRAL = ProviderConfig(
    name="mistral",
    base_url="https://api.mistral.ai/v1",
    api_key_env="MISTRAL_API_KEY",
    model_env="MISTRAL_MODEL",
    # Experiment tier: 1 req/s.
    min_interval_s=2.0,
)

# Note (issue #7 AC4): unlike Gemini/Mistral, Groq's response headers don't
# expose remaining RPD (requests-per-day) quota, so it's tracked locally
# instead (issue #9) — 1,000 RPD is the free-tier limit of the model
# currently set in GROQ_MODEL (console.groq.com/docs/rate-limits).
GROQ = ProviderConfig(
    name="groq",
    base_url="https://api.groq.com/openai/v1",
    api_key_env="GROQ_API_KEY",
    model_env="GROQ_MODEL",
    daily_limit=1000,
    # 30 RPM but only 8k TPM, and one chapter is ~5-7k tokens: ~1 req/min.
    min_interval_s=60.0,
)

OPENROUTER_HEADERS = {
    "HTTP-Referer": "https://github.com/EPF-MDE/GUESS.ARC",
    "X-Title": "GUESS.ARC taxonomy tagger",
}

# Dynamic-catalog OpenRouter config (issue #8): resolves a `:free` model at
# call time via GET /models?max_price=0 instead of a hardcoded id. Kept
# available (e.g. for direct/manual use) but deliberately left out of
# PROVIDERS/FALLBACK_CHAIN below: picking blindly off the rotating catalog
# can land on a model whose free endpoint doesn't accept our response_format,
# which OpenRouter answers with a raw 400 that isn't retried or fallen over —
# it just crashes the run (observed in practice). The fixed-model configs
# below replace it for actual benchmark/production use.
OPENROUTER = ProviderConfig(
    name="openrouter",
    base_url="https://openrouter.ai/api/v1",
    api_key_env="OPENROUTER_API_KEY",
    model_env="OPENROUTER_MODEL",
    resolve_model_from_catalog=True,
    extra_headers=OPENROUTER_HEADERS,
    daily_limit=50,
    # :free models: 20 RPM.
    min_interval_s=3.0,
)

# Each model we want to benchmark via OpenRouter is its own fixed-model
# ProviderConfig, confirmed (via GET /models) to advertise `response_format`
# support. Each writes to its own data/taxonomy/<name>/ — never a shared
# data/taxonomy/openrouter/ — so the 3 models stay directly comparable, same
# as gemini/mistral/groq.
#
# All three share one OpenRouter API key and its 50 req/day free-tier cap
# (issue #9), so they share one quota_key ("openrouter") rather than each
# getting their own 50 in quota_state.json.
OPENROUTER_NEMOTRON = ProviderConfig(
    name="openrouter-nemotron",
    base_url="https://openrouter.ai/api/v1",
    api_key_env="OPENROUTER_API_KEY",
    model_env="OPENROUTER_NEMOTRON_MODEL",
    extra_headers=OPENROUTER_HEADERS,
    daily_limit=50,
    quota_key="openrouter",
    min_interval_s=3.0,
)

OPENROUTER_NEX_PRO = ProviderConfig(
    name="openrouter-nex-pro",
    base_url="https://openrouter.ai/api/v1",
    api_key_env="OPENROUTER_API_KEY",
    model_env="OPENROUTER_NEX_PRO_MODEL",
    extra_headers=OPENROUTER_HEADERS,
    daily_limit=50,
    quota_key="openrouter",
    min_interval_s=3.0,
)

OPENROUTER_DOTS = ProviderConfig(
    name="openrouter-dots",
    base_url="https://openrouter.ai/api/v1",
    api_key_env="OPENROUTER_API_KEY",
    model_env="OPENROUTER_DOTS_MODEL",
    extra_headers=OPENROUTER_HEADERS,
    daily_limit=50,
    quota_key="openrouter",
    min_interval_s=3.0,
)

PROVIDERS = {
    "gemini": GEMINI,
    "mistral": MISTRAL,
    "groq": GROQ,
    "openrouter-nemotron": OPENROUTER_NEMOTRON,
    "openrouter-nex-pro": OPENROUTER_NEX_PRO,
    "openrouter-dots": OPENROUTER_DOTS,
}

# Ordered fallback chain (issue #6): tried in this order, Gemini first, then
# Mistral (#6), Groq (#7), then the 3 fixed OpenRouter models (#8) as the
# last relays — never branch on provider name in the call/fallback logic
# itself.
FALLBACK_CHAIN = ["gemini", "mistral", "groq", "openrouter-nemotron", "openrouter-nex-pro", "openrouter-dots"]
