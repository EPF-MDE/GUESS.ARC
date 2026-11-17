"""Vectorisation de la silver en Chapter embeddings, dans data/gold/vector/.

    encoder   -> protocole Encoder, injecté dans `run`
    pipeline  -> `run(data_dir, encoder, rebuild=False)` : silver -> Scenes -> Chapter embeddings,
                 incrémental (un chapitre inchangé garde son Chapter embedding) ;
                 `main` : `python -m guess_arc.vectorisation`, EMBEDDING_MODEL lu dans le .env
    dataset   -> écriture atomique du .npz, `load_chapter_embeddings` et `corrupt_verification`
    quality   -> rapport qualité embeddings_quality.json, à côté du dataset
    sentence_encoder -> l'Encoder réel (sentence-transformers, extra [vectorisation])
"""

from .dataset import ChapterEmbeddings, CorruptDatasetError, Metadata, load_chapter_embeddings
from .encoder import Encoder
from .pipeline import RunResult, run

__all__ = ["ChapterEmbeddings", "CorruptDatasetError", "Encoder", "Metadata", "load_chapter_embeddings", "RunResult", "run"]
