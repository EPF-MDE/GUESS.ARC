"""Appel au modèle pour un chapitre : essais, pause, réponses brutes et journal.

- au plus `max_attempts` essais par chapitre ; une réponse invalide (ou une
  erreur du client) déclenche un nouvel essai ;
- `pause_s` secondes entre la fin d'un appel et le début du suivant, y compris
  entre deux essais (règle du serveur de l'école) ;
- chaque réponse brute est écrite dans `raw/events_NNNN_attempt_N.json`, telle
  que le serveur l'a renvoyée ;
- `run.jsonl` reçoit une ligne par appel : chapitre, essai, durée, tokens,
  erreur et issue (`ok`, `retry`, `abandoned`).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .llm import LLMClient
from .response import InvalidResponse, parse_response

PAUSE_S = 15.0
MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class Extraction:
    document: dict
    attempts: int
    model: str


class Pacer:
    """Fait respecter la pause entre deux appels, quel que soit le chapitre."""

    def __init__(self, pause_s: float):
        self.pause_s = pause_s
        self._last_end: float | None = None

    def wait(self) -> None:
        if self._last_end is not None:
            remaining = self.pause_s - (time.monotonic() - self._last_end)
            if remaining > 0:
                time.sleep(remaining)

    def call_ended(self) -> None:
        self._last_end = time.monotonic()


def _log(log_path: Path, line: dict) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def extract_chapter(client: LLMClient, chapter: int, system: str, user: str, schema: dict,
                    raw_dir: Path, log_path: Path, pacer: Pacer,
                    max_attempts: int = MAX_ATTEMPTS) -> Extraction | None:
    """Événements renvoyés par le modèle, ou None si tous les essais ont échoué."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, max_attempts + 1):
        pacer.wait()
        started = time.monotonic()
        completion, document, error = None, None, None
        try:
            completion = client.complete(system, user, schema)
        except Exception as e:  # un passage de plusieurs heures ne s'arrête pas sur un appel
            error = f"{type(e).__name__}: {e}"
        finally:
            pacer.call_ended()
        duration = time.monotonic() - started
        if completion is not None:
            (raw_dir / f"events_{chapter:04d}_attempt_{attempt}.json").write_text(
                completion.text, encoding="utf-8")
            try:
                document = parse_response(completion.text, schema, chapter)
            except InvalidResponse as e:
                error = str(e)
        outcome = ("ok" if document is not None
                   else "abandoned" if attempt == max_attempts else "retry")
        _log(log_path, {
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "chapter": chapter,
            "attempt": attempt,
            "duration_s": round(duration, 3),
            "prompt_tokens": completion.prompt_tokens if completion else None,
            "completion_tokens": completion.completion_tokens if completion else None,
            "error": error,
            "outcome": outcome,
        })
        if document is not None:
            return Extraction(document, attempt, client.model)
    return None
