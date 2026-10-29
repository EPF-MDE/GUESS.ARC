"""Client LLM HTTP, configuré uniquement par le `.env` à la racine du repo.

Cinq variables, toutes requises, sans aucune valeur par défaut dans le code
(voir .env.example) :

- `LLM_BASE_URL`  : adresse du serveur ;
- `LLM_API_KEY`   : clé envoyée en `Authorization: Bearer` ;
- `LLM_MODEL`     : identifiant exact du modèle ;
- `LLM_API`       : forme de la route, `openai` (chat completions compatible
                    OpenAI) ou `ollama` (API native d'Ollama) ;
- `LLM_CHAT_PATH` : chemin de la route sur le serveur.

Seul le fichier `.env` est lu, jamais les variables d'environnement du shell :
la configuration d'un passage est celle du fichier, et rien d'autre.

Paramètres d'appel fixes : température 0, graine fixe, contexte de 16 384
tokens, réponse de 3 000 tokens au plus, expiration à 10 minutes, mode
« thinking » désactivé. La route `openai` n'a pas de champ standard pour le
contexte ni la réflexion : `num_ctx`, `think` et `chat_template_kwargs` y sont
ajoutés pour les serveurs qui les transmettent (Open WebUI vers Ollama, vLLM),
et ignorés des autres. scripts/llm/diagnostic_serveur.py vérifie, à la main,
quelle route applique vraiment le schéma et tient un appel de ~10 000 tokens.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import requests

from guess_arc import paths

from .llm import Completion

TEMPERATURE = 0
SEED = 42
CONTEXT_TOKENS = 16384
MAX_TOKENS = 3000
TIMEOUT_S = 600

APIS = ("openai", "ollama")
VARIABLES = ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "LLM_API", "LLM_CHAT_PATH")


class ConfigError(ValueError):
    pass


def read_env_file(path: Path) -> dict[str, str]:
    """Lignes `NOM=valeur` ; commentaires, lignes vides et `export ` ignorés,
    guillemets autour de la valeur retirés."""
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.removeprefix("export ").split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[name.strip()] = value
    return values


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    api: str
    chat_path: str

    @classmethod
    def from_env_file(cls, path: Path = paths.ENV_PATH) -> LLMConfig:
        if not path.is_file():
            raise ConfigError(f"fichier {path} introuvable : le créer à partir de "
                              ".env.example")
        values = read_env_file(path)
        missing = [name for name in VARIABLES if not values.get(name)]
        if missing:
            raise ConfigError(f"variables manquantes ou vides dans {path} : "
                              f"{', '.join(missing)} (voir .env.example)")
        if values["LLM_API"] not in APIS:
            raise ConfigError(f"LLM_API={values['LLM_API']!r} dans {path} : "
                              f"attendu {' ou '.join(APIS)}")
        return cls(base_url=values["LLM_BASE_URL"].rstrip("/"),
                   api_key=values["LLM_API_KEY"], model=values["LLM_MODEL"],
                   api=values["LLM_API"], chat_path=values["LLM_CHAT_PATH"])


class HttpClient:
    def __init__(self, config: LLMConfig):
        self.config = config
        self.model = config.model

    def request(self, system: str, user: str, schema: dict) -> tuple[str, dict, dict]:
        """URL, en-têtes et corps de l'appel, sans l'envoyer."""
        cfg = self.config
        url = cfg.base_url + "/" + cfg.chat_path.lstrip("/")
        headers = {"Content-Type": "application/json",
                   "Authorization": f"Bearer {cfg.api_key}"}
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": user}]
        if cfg.api == "openai":
            payload = {
                "model": cfg.model, "messages": messages, "stream": False,
                "temperature": TEMPERATURE, "seed": SEED, "max_tokens": MAX_TOKENS,
                "response_format": {"type": "json_schema", "json_schema": {
                    "name": "chapter_events", "schema": schema, "strict": True}},
                "num_ctx": CONTEXT_TOKENS, "think": False,
                "chat_template_kwargs": {"enable_thinking": False},
            }
        else:
            payload = {
                "model": cfg.model, "messages": messages, "stream": False,
                "format": schema, "think": False,
                "options": {"temperature": TEMPERATURE, "seed": SEED,
                            "num_ctx": CONTEXT_TOKENS, "num_predict": MAX_TOKENS},
            }
        return url, headers, payload

    def completion(self, body: dict) -> Completion:
        """Texte et tokens d'une réponse du serveur."""
        try:
            if self.config.api == "openai":
                usage = body.get("usage") or {}
                return Completion(body["choices"][0]["message"]["content"],
                                  usage.get("prompt_tokens"), usage.get("completion_tokens"))
            return Completion(body["message"]["content"],
                              body.get("prompt_eval_count"), body.get("eval_count"))
        except (KeyError, IndexError, TypeError):
            raise ValueError(f"réponse inattendue du serveur : {str(body)[:300]}") from None

    def complete(self, system: str, user: str, schema: dict) -> Completion:
        url, headers, payload = self.request(system, user, schema)
        r = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT_S)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code} : {r.text[:300]}")
        return self.completion(r.json())
