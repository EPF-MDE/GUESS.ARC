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
    default_model: str

    def api_key(self) -> str:
        key = os.environ.get(self.api_key_env)
        if not key:
            raise RuntimeError(
                f"{self.api_key_env} is not set — see API/README.md, "
                f"then set it in the root .env"
            )
        return key

    def model(self) -> str:
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
# expose remaining RPD (requests-per-day) quota — a future quota counter
# (next ticket) can't read it off Groq responses and must track Groq usage
# some other way (e.g. counting calls locally).
GROQ = ProviderConfig(
    name="groq",
    base_url="https://api.groq.com/openai/v1",
    api_key_env="GROQ_API_KEY",
    model_env="GROQ_MODEL",
    default_model="openai/gpt-oss-120b",
)

PROVIDERS = {"gemini": GEMINI, "mistral": MISTRAL, "groq": GROQ}

# Ordered fallback chain (issue #6): tried in this order, Gemini first. Future
# tickets (#8 OpenRouter) extend this list — never branch on provider name in
# the call/fallback logic itself.
FALLBACK_CHAIN = ["gemini", "mistral", "groq"]
