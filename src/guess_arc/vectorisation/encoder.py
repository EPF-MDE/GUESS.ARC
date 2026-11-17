"""Le protocole Encoder : seul point de contact entre la vectorisation et le modèle.

L'encodeur réel (sentence-transformers) et les encodeurs factices des tests le
respectent ; tout le reste de la vectorisation n'en connaît que ces quatre membres.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np


class Encoder(Protocol):
    @property
    def model_name(self) -> str:
        """Identifiant du modèle, stocké dans le dataset pour détecter un changement."""
        ...

    @property
    def max_tokens(self) -> int:
        """Fenêtre maximale de l'encodeur, en tokens."""
        ...

    def count_tokens(self, text: str) -> int:
        """Nombre de tokens de `text` pour ce modèle."""
        ...

    def encode(self, texts: list[str]) -> np.ndarray:
        """Un vecteur par texte : tableau N × d, dans l'ordre de `texts`."""
        ...
