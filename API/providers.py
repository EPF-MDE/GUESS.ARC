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
    # None means "no fixed model — resolve one at call time" (issue #8:
    # OpenRouter's free catalog changes over time, so it's never hardcoded
    # here). `model_env` still overrides it when set, same as every provider.
    default_model: str | None
    # Static headers to send with every request to this provider (issue #8:
    # OpenRouter's HTTP-Referer/X-Title). None for providers that need none.
    extra_headers: dict[str, str] | None = None
    # Local daily request budget enforced by quota_state.py (issue #9). None
    # means "not locally tracked" — Gemini/Mistral expose their remaining RPD
    # in response headers, so a local counter isn't needed for them (yet).
    daily_limit: int | None = None

    def api_key(self) -> str:
        key = os.environ.get(self.api_key_env)
        if not key:
            raise RuntimeError(
                f"{self.api_key_env} is not set — see API/README.md, "
                f"then set it in the root .env"
            )
        return key

    def model(self) -> str | None:
        return os.environ.get(self.model_env) or self.default_model


GEMINI = ProviderConfig(
    name="gemini",
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    api_key_env="GEMINI_API_KEY",
    model_env="GEMINI_MODEL",
    default_model="gemini-2.5-flash",
)

MISTRAL = ProviderConfig(
    name="mistral",
    base_url="https://api.mistral.ai/v1",
    api_key_env="MISTRAL_API_KEY",
    model_env="MISTRAL_MODEL",
    default_model="mistral-small-latest",
)

# `llama-3.3-70b-versatile` was deprecated on Groq's free tier on 2026-06-17;
# `openai/gpt-oss-120b` replaces it (issue #7).
#
# Note (issue #7 AC4): unlike Gemini/Mistral, Groq's response headers don't
# expose remaining RPD (requests-per-day) quota, so it's tracked locally
# instead (issue #9) — 1,000 RPD is the free-tier limit for
# openai/gpt-oss-120b (console.groq.com/docs/rate-limits).
GROQ = ProviderConfig(
    name="groq",
    base_url="https://api.groq.com/openai/v1",
    api_key_env="GROQ_API_KEY",
    model_env="GROQ_MODEL",
    default_model="openai/gpt-oss-120b",
    daily_limit=1000,
)

OPENROUTER = ProviderConfig(
    name="openrouter",
    base_url="https://openrouter.ai/api/v1",
    api_key_env="OPENROUTER_API_KEY",
    model_env="OPENROUTER_MODEL",
    # No hardcoded id (issue #8 acceptance criteria): the free catalog rotates,
    # so taxonomy_client.py resolves a `:free` model via GET /models?max_price=0
    # at call time whenever this is None and OPENROUTER_MODEL isn't set.
    default_model=None,
    extra_headers={
        "HTTP-Referer": "https://github.com/EPF-MDE/GUESS.ARC",
        "X-Title": "GUESS.ARC taxonomy tagger",
    },
    # Hard-capped at 50 requests/day without purchased credits (issue #9).
    daily_limit=50,
)

PROVIDERS = {"gemini": GEMINI, "mistral": MISTRAL, "groq": GROQ, "openrouter": OPENROUTER}

# Ordered fallback chain (issue #6): tried in this order, Gemini first, then
# Mistral (#6), Groq (#7), OpenRouter as the 4th and last relay (#8) — never
# branch on provider name in the call/fallback logic itself.
FALLBACK_CHAIN = ["gemini", "mistral", "groq", "openrouter"]
