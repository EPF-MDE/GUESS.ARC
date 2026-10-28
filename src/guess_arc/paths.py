"""Emplacements des couches de données, ancrés sur la racine du repo.

Ancrés sur le repo et non sur le dossier courant : chaque étape (ingestion,
extraction des événements, puis features et modèle) lit et écrit au même endroit, d'où
qu'on la lance. Suppose une installation éditable (`pip install -e .`).
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
# Décisions de relecture des fuites du futur : versionnées, donc hors de data/.
FUTURE_LEAK_REVIEW_PATH = REPO_ROOT / "review" / "future_leaks.json"


def bronze_dir(data_dir: Path = DATA_DIR) -> Path:
    return data_dir / "bronze"


def silver_dir(data_dir: Path = DATA_DIR) -> Path:
    return data_dir / "silver"


def state_path(data_dir: Path = DATA_DIR) -> Path:
    return data_dir / "state.json"


def event_dir(data_dir: Path = DATA_DIR) -> Path:
    return data_dir / "event"


def event_in_dir(data_dir: Path = DATA_DIR) -> Path:
    """Prompts utilisateur exacts, un `events_NNNN.md` par chapitre."""
    return event_dir(data_dir) / "in"


def event_out_dir(data_dir: Path = DATA_DIR) -> Path:
    """Événements extraits, un `events_NNNN.json` par chapitre."""
    return event_dir(data_dir) / "out"


def event_raw_dir(data_dir: Path = DATA_DIR) -> Path:
    """Réponses brutes du modèle, une par essai (hors git)."""
    return event_dir(data_dir) / "raw"


def event_run_log_path(data_dir: Path = DATA_DIR) -> Path:
    """Journal d'exécution, une ligne JSON par appel au modèle."""
    return event_dir(data_dir) / "run.jsonl"


def event_leak_candidates_path(data_dir: Path = DATA_DIR) -> Path:
    """Fuites du futur repérées au dernier préparsing, avec leur décision de relecture."""
    return event_dir(data_dir) / "future_leak_candidates.json"
