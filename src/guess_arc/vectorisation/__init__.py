"""Vectorisation de la silver en Chapter embeddings, dans data/gold/vector/.

    encoder   -> protocole Encoder, injecté dans `run`
    pipeline  -> `run(data_dir, encoder)` : silver -> Scenes -> Chapter embeddings
    dataset   -> écriture atomique du .npz et `load_chapter_embeddings`
    quality   -> rapport qualité embeddings_quality.json, à côté du dataset
    sentence_encoder -> l'Encoder réel (sentence-transformers, extra [vectorisation])
    cli       -> `python -m guess_arc.vectorisation` : EMBEDDING_MODEL lu dans le .env
"""

from .dataset import ChapterEmbeddings, Metadata, load_chapter_embeddings
from .encoder import Encoder
from .pipeline import RunResult, run

__all__ = ["ChapterEmbeddings", "Encoder", "Metadata", "load_chapter_embeddings", "RunResult", "run"]
