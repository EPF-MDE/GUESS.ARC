"""Emplacements des couches de données, ancrés sur la racine du repo.

Ancrés sur le repo et non sur le dossier courant : chaque étape (ingestion
aujourd'hui, features et modèle demain) lit et écrit au même endroit, d'où
qu'on la lance. Suppose une installation éditable (`pip install -e .`).
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
# Données de référence versionnées (datasets, listes tenues à la main), à part
# des couches générées de data/.
REFERENCE_DIR = REPO_ROOT / "reference"
# Réglages versionnés des étapes (modèle LLM choisi, etc.), sans secret : les clés d'API
# viennent de l'environnement.
CONFIG_DIR = REPO_ROOT / "configs"


def bronze_dir(data_dir: Path = DATA_DIR) -> Path:
    return data_dir / "bronze"


def silver_dir(data_dir: Path = DATA_DIR) -> Path:
    return data_dir / "silver"


def gold_dir(data_dir: Path = DATA_DIR) -> Path:
    return data_dir / "gold"


def llm_cache_dir(data_dir: Path = DATA_DIR) -> Path:
    """Réponses brutes des LLM, archivées comme le wikitext : une source externe, donc en bronze."""
    return bronze_dir(data_dir) / "llm"


def state_path(data_dir: Path = DATA_DIR) -> Path:
    return data_dir / "state.json"
