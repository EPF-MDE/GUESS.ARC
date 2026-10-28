"""Client LLM : une seule opération, (prompt système, prompt utilisateur, schéma) -> texte brut.

Le texte est rendu tel que le serveur l'a écrit, avec un éventuel bloc de
réflexion : c'est le pipeline qui le retire, le parse et le valide. Le client
peut aussi rapporter les tokens consommés, notés dans le journal.

Le client HTTP configuré par le `.env` viendra à côté (#98) ; `FakeClient`
sert aux tests et renvoie des réponses écrites à l'avance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Completion:
    text: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class LLMClient(Protocol):
    model: str

    def complete(self, system: str, user: str, schema: dict) -> Completion: ...


@dataclass(frozen=True)
class Call:
    system: str
    user: str
    schema: dict


class FakeClient:
    """Renvoie, appel après appel, les réponses données (texte ou `Completion`) ;
    une exception est levée."""

    def __init__(self, responses: list[str | Completion | Exception], model: str = "fake"):
        self.model = model
        self._responses = list(responses)
        self.calls: list[Call] = []

    def complete(self, system: str, user: str, schema: dict) -> Completion:
        self.calls.append(Call(system, user, schema))
        if not self._responses:
            raise RuntimeError("client factice : plus de réponse écrite à l'avance")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response if isinstance(response, Completion) else Completion(response)
