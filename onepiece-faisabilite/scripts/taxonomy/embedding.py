"""Encodage vectoriel des termes candidats, avec repli local si le modèle
d'embedding n'est pas téléchargeable (pas d'accès réseau à Hugging Face).

Mode principal : sentence-transformers, modèle multilingue léger
(paraphrase-multilingual-MiniLM-L12-v2). Il gère aussi bien l'anglais du
corpus que le français d'une prédiction manuscrite, ce qui permet de comparer
les deux dans le même espace vectoriel.

Mode de repli : TF-IDF sur des n-grams de caractères (2 à 4), qui ne demande
aucun téléchargement. Moins précis sémantiquement (pas de vraie synonymie),
mais robuste aux variantes orthographiques d'un même terme.

Le choix du mode est persisté dans `embedder_meta.json` pour que
`04_tag_text.py` réutilise exactement le même encodage que celui utilisé pour
construire la taxonomie (indispensable pour que la similarité cosinus ait un
sens).
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np

DEFAULT_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class Embedder:
    """Encode une liste de termes en vecteurs, quel que soit le mode actif."""

    def __init__(self, mode: str, model=None, vectorizer=None, model_name: str | None = None):
        self.mode = mode  # "sentence-transformers" ou "tfidf"
        self._model = model
        self._vectorizer = vectorizer
        self.model_name = model_name

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim))
        if self.mode == "sentence-transformers":
            return np.asarray(self._model.encode(texts, show_progress_bar=False))
        matrix = self._vectorizer.transform(texts)
        return np.asarray(matrix.todense())

    @property
    def dim(self) -> int:
        if self.mode == "sentence-transformers":
            return self._model.get_sentence_embedding_dimension()
        return len(self._vectorizer.get_feature_names_out())

    def save(self, output_dir: Path) -> None:
        """Sauvegarde la config du mode. Le vectorizer TF-IDF est picklé à part."""
        meta = {"mode": self.mode, "model_name": self.model_name}
        (output_dir / "embedder_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if self.mode == "tfidf":
            joblib.dump(self._vectorizer, output_dir / "tfidf_vectorizer.joblib")

    @classmethod
    def load(cls, output_dir: Path) -> "Embedder":
        """Recharge l'embedder utilisé lors de la construction de la taxonomie."""
        meta = json.loads((output_dir / "embedder_meta.json").read_text(encoding="utf-8"))
        if meta["mode"] == "sentence-transformers":
            return cls.build(model_name=meta["model_name"])
        vectorizer = joblib.load(output_dir / "tfidf_vectorizer.joblib")
        return cls(mode="tfidf", vectorizer=vectorizer)

    @classmethod
    def build(cls, model_name: str = DEFAULT_MODEL_NAME, fit_corpus: list[str] | None = None) -> "Embedder":
        """Construit un embedder : tente sentence-transformers, sinon TF-IDF.

        `fit_corpus` n'est utilisé qu'en mode de repli, pour ajuster le
        vectorizer TF-IDF (nécessaire uniquement lors de la construction
        initiale, pas lors d'un rechargement).
        """
        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(model_name)
            print(f"[embedding] mode sentence-transformers ({model_name}).")
            return cls(mode="sentence-transformers", model=model, model_name=model_name)
        except Exception as exc:
            print(f"[embedding] sentence-transformers indisponible ({exc!r}) -> repli TF-IDF.")
            from sklearn.feature_extraction.text import TfidfVectorizer

            vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
            if fit_corpus:
                vectorizer.fit(fit_corpus)
            return cls(mode="tfidf", vectorizer=vectorizer)
