"""L'encodeur réel : un modèle sentence-transformers, gelé, sur CPU (ADR 0003).

sentence-transformers est dans l'extra pip optionnel [vectorisation] : il n'est
importé qu'à la construction de l'encodeur, pour que le reste du package
s'importe sans lui.
"""

from __future__ import annotations

import numpy as np

PIP_COMMAND = "pip install -e .[vectorisation]"


class MissingExtraError(RuntimeError):
    """sentence-transformers n'est pas installé."""


class SentenceTransformerEncoder:
    """Respecte le protocole Encoder. Le nom du modèle vient du .env, jamais du code."""

    def __init__(self, model_name: str):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise MissingExtraError(
                f"sentence-transformers n'est pas installé. Lancer : {PIP_COMMAND}"
            ) from exc
        self._model_name = model_name
        self._model = SentenceTransformer(model_name, device="cpu")

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def max_tokens(self) -> int:
        # Fenêtre utile pour le texte : sans les tokens spéciaux ([CLS], [SEP]),
        # que count_tokens ne compte pas.
        return int(self._model.max_seq_length) - self._model.tokenizer.num_special_tokens_to_add()

    def count_tokens(self, text: str) -> int:
        return len(self._model.tokenizer(text, add_special_tokens=False)["input_ids"])

    def encode(self, texts: list[str]) -> np.ndarray:
        return self._model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
