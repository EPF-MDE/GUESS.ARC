"""Prompt système de l'appel au modèle, commun à tous les chapitres (`PROMPT_VERSION`).

Assemblé à partir de prompts/ :

    system.md           -> consignes, avec les emplacements {{TYPES}},
                           {{EXAMPLE_INPUT}} et {{EXAMPLE_OUTPUT}}
    example_0097.md     -> prompt utilisateur du ch. 97, figé tel que le
                           préparsing l'a produit (exemple few-shot)
    example_0097.json   -> sortie attendue, rédigée à la main : granularité et
                           piège de « Smoker is introduced »

Le ch. 97 de l'exemple est figé : il ne suit pas la silver, et le modifier
change le prompt, donc sa version. Le prompt ne commence pas par le jeton qui
active le mode « thinking » de Gemma 4.
"""

from __future__ import annotations

import json
from pathlib import Path

from .taxonomy import LLM_EVENT_TYPES

PROMPTS_DIR = Path(__file__).parent / "prompts"


def _read(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def example_output() -> dict:
    return json.loads(_read("example_0097.json"))


def system_prompt() -> str:
    types = "\n".join(f"- {name}: {definition}"
                      for name, definition in LLM_EVENT_TYPES.items())
    output = json.dumps(example_output(), ensure_ascii=False, indent=2)
    return (_read("system.md")
            .replace("{{TYPES}}", types)
            .replace("{{EXAMPLE_INPUT}}", _read("example_0097.md"))
            .replace("{{EXAMPLE_OUTPUT}}", output))
