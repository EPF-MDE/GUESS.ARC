"""Emplacements des couches de données, ancrés sur la racine du repo.

Ancrés sur le repo et non sur le dossier courant : chaque étape (ingestion
aujourd'hui, features et modèle demain) lit et écrit au même endroit, d'où
qu'on la lance. Suppose une installation éditable (`pip install -e .`).
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"


def bronze_dir(data_dir: Path = DATA_DIR) -> Path:
    return data_dir / "bronze"


def silver_dir(data_dir: Path = DATA_DIR) -> Path:
    return data_dir / "silver"


def gold_dir(data_dir: Path = DATA_DIR) -> Path:
    return data_dir / "gold"


def state_path(data_dir: Path = DATA_DIR) -> Path:
    return data_dir / "state.json"
