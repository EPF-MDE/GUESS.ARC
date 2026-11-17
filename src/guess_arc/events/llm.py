"""Backend LLM partagé par la découverte des Event types et l'extraction des Events.

- Le modèle ('fournisseur:nom') est un réglage de configs/events.json, un par tâche ; ajouter un
  fournisseur, c'est ajouter un adaptateur à PROVIDERS, sans toucher aux appelants.
- Un appel = un prompt + un schéma JSON ; la réponse est validée contre le schéma, sinon
  StructuredOutputError (jamais acceptée en silence, jamais mise en cache).
- Température 0 partout où le fournisseur l'accepte (voir AnthropicBackend pour l'exception).
- Cache des réponses par (modèle, version du prompt, version de la taxonomie, chapitre) dans
  data/bronze/llm/ : un second run identique ne fait aucun appel réseau.
- FakeBackend : réponses écrites d'avance, pour les tests.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import jsonschema

from guess_arc import paths

EVENTS_CONFIG = paths.CONFIG_DIR / "events.json"


class StructuredOutputError(ValueError):
    """La réponse du modèle n'est pas du JSON conforme au schéma demandé."""


# Chaque partie de la clé devient un dossier du cache : lettres, chiffres, '.', '_' et '-' seulement.
_SAFE_PART = re.compile(r"[A-Za-z0-9._-]+")


def split_model(model: str) -> tuple[str, str]:
    """'anthropic:claude-opus-5-5' -> ('anthropic', 'claude-opus-5-5')."""
    provider, sep, name = model.partition(":")
    if not sep or not provider or not name:
        raise ValueError(f"model {model!r} must be written 'provider:model-name'")
    return provider, name


@dataclass(frozen=True)
class LlmRequest:
    prompt: str
    schema: dict
    prompt_version: str
    taxonomy_version: str
    chapter: int


class Backend(Protocol):
    """Un adaptateur par fournisseur. Contrat : température 0 quand l'API l'accepte."""

    model: str  # 'fournisseur:nom', p. ex. 'anthropic:claude-opus-5-5'

    def complete(self, prompt: str, schema: dict) -> str:
        """Le texte JSON de la réponse ; StructuredOutputError si elle est inachevée."""
        ...


class FakeBackend:
    """Renvoie toujours `response` et compte ses appels : aucun test ne touche le réseau."""

    def __init__(self, response, model: str = "fake:canned") -> None:
        self.model = model
        self._response = response
        self.calls = 0

    def complete(self, prompt: str, schema: dict) -> str:
        self.calls += 1
        # Une chaîne passe telle quelle : c'est ainsi qu'on simule une réponse qui n'est pas du JSON.
        if isinstance(self._response, str):
            return self._response
        return json.dumps(self._response)


class LlmClient:
    def __init__(self, backend: Backend, cache_dir: Path | None = None) -> None:
        self.backend = backend
        self.cache_dir = cache_dir if cache_dir is not None else paths.llm_cache_dir()

    def call(self, request: LlmRequest) -> dict:
        """La sortie structurée validée, depuis le cache si cette clé a déjà été appelée."""
        path = self.cache_path(request)
        if path.exists():
            output = json.loads(path.read_text(encoding="utf-8"))["response"]
            # Revalidée : un schéma changé sans nouvelle version du prompt ne passe pas en silence.
            self._validate(output, request.schema,
                           f"{self.backend.model}, chapter {request.chapter}: cached answer {path}",
                           hint="; bump the prompt version after changing a prompt or schema")
            return output
        output = self._complete_and_validate(request)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "model": self.backend.model,
            "prompt_version": request.prompt_version,
            "taxonomy_version": request.taxonomy_version,
            "chapter": request.chapter,
            "response": output,
        }
        # Écrit à côté puis renommé : un run interrompu ne laisse pas de fichier tronqué en cache.
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        return output

    def cache_path(self, request: LlmRequest) -> Path:
        """Un fichier par clé (modèle, version du prompt, version de la taxonomie, chapitre)."""
        provider, name = split_model(self.backend.model)
        parts = [provider, name, request.prompt_version, request.taxonomy_version]
        for part in parts:
            if not _SAFE_PART.fullmatch(part) or part.strip(".") == "":
                raise ValueError(f"cache key part {part!r} is not a safe folder name")
        return self.cache_dir.joinpath(*parts, f"chapter_{request.chapter:04d}.json")

    def _complete_and_validate(self, request: LlmRequest) -> dict:
        where = f"{self.backend.model}, chapter {request.chapter}"
        try:
            raw = self.backend.complete(request.prompt, request.schema)
        except StructuredOutputError as exc:
            raise StructuredOutputError(f"{where}: {exc}") from exc
        try:
            output = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise StructuredOutputError(f"{where}: response is not JSON ({exc})") from exc
        self._validate(output, request.schema, where)
        return output

    @staticmethod
    def _validate(output, schema: dict, where: str, hint: str = "") -> None:
        try:
            jsonschema.validate(output, schema)
        except jsonschema.ValidationError as exc:
            raise StructuredOutputError(
                f"{where}: response does not match the schema ({exc.message}){hint}"
            ) from exc


class AnthropicBackend:
    """Claude via le SDK officiel ; la clé vient de l'environnement (ANTHROPIC_API_KEY).

    Pas de `temperature` : depuis la version d'API 2026-10-21, l'API Anthropic refuse tout
    paramètre d'échantillonnage (erreur 400), sur tous les modèles. La reproductibilité vient
    du cache de LlmClient. Aucun repli (*fallback*) vers un autre modèle n'est demandé : la
    réponse doit venir du modèle nommé dans la clé du cache.
    """

    MAX_TOKENS = 16000

    def __init__(self, model_name: str, client=None) -> None:
        self.model = f"anthropic:{model_name}"
        self.model_name = model_name
        self._client = client

    def complete(self, prompt: str, schema: dict) -> str:
        if self._client is None:
            import anthropic  # ici seulement : construire le backend ne demande pas de clé

            self._client = anthropic.Anthropic()
        message = self._client.messages.create(
            model=self.model_name,
            max_tokens=self.MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        if message.stop_reason != "end_turn":
            raise StructuredOutputError(f"answer stopped early (stop_reason {message.stop_reason!r})")
        text = next((block.text for block in message.content if block.type == "text"), None)
        if text is None:
            raise StructuredOutputError("answer has no text block")
        return text


# Un fournisseur de plus = un adaptateur de plus ici, sans toucher aux appelants.
PROVIDERS = {"anthropic": AnthropicBackend}


def backend_from_config(task: str, config_path: Path = EVENTS_CONFIG) -> Backend:
    """Le backend du modèle que la config donne à `task` ('discovery' ou 'extraction')."""
    config = json.loads(config_path.read_text(encoding="utf-8"))
    key = f"{task}_model"
    if key not in config:
        raise ValueError(f"{config_path} has no {key!r}; it has {sorted(config)}")
    provider, name = split_model(config[key])
    if provider not in PROVIDERS:
        raise ValueError(f"unknown LLM provider {provider!r}; known providers: {sorted(PROVIDERS)}")
    return PROVIDERS[provider](name)
