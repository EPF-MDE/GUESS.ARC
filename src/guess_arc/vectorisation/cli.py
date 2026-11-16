"""Vectorise la silver en Chapter embeddings, dans data/gold/vector/.

Le modèle se règle dans le .env (EMBEDDING_MODEL). Nécessite l'extra
[vectorisation] : pip install -e .[vectorisation]
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Callable, Mapping
from pathlib import Path

from guess_arc import paths

from .encoder import Encoder
from .pipeline import run
from .sentence_encoder import MissingExtraError, SentenceTransformerEncoder

SETTING = "EMBEDDING_MODEL"
ENV_FILE = paths.REPO_ROOT / ".env"


class MissingSettingError(RuntimeError):
    """EMBEDDING_MODEL n'est réglé ni dans l'environnement ni dans le .env."""


def _read_env_file(env_file: Path) -> dict[str, str]:
    if not env_file.is_file():
        return {}
    values = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def embedding_model(environ: Mapping[str, str], env_file: Path = ENV_FILE) -> str:
    """Le modèle à utiliser : variable d'environnement, sinon ligne du .env."""
    model = environ.get(SETTING) or _read_env_file(env_file).get(SETTING)
    if not model:
        raise MissingSettingError(
            f"{SETTING} absent : l'ajouter au fichier {env_file}, par exemple "
            f"{SETTING}=<identifiant Hugging Face du modèle> (voir le README)"
        )
    return model


def main(
    argv: list[str] | None = None,
    *,
    environ: Mapping[str, str] = os.environ,
    env_file: Path = ENV_FILE,
    make_encoder: Callable[[str], Encoder] = SentenceTransformerEncoder,
) -> None:
    p = argparse.ArgumentParser(prog="python -m guess_arc.vectorisation", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", type=Path, default=paths.DATA_DIR,
                   help="racine des couches silver/gold (défaut : data/ à la racine du repo)")
    args = p.parse_args(argv)

    try:
        encoder = make_encoder(embedding_model(environ, env_file))
    except (MissingSettingError, MissingExtraError) as exc:
        raise SystemExit(f"erreur : {exc}") from exc

    result = run(args.data_dir, encoder)
    print(f"chapitres vectorisés : {len(result.vectorised)}, sautés : {len(result.skipped)} "
          f"-> {result.path}")
    if result.skipped:
        print("sautés : " + ", ".join(f"{c} ({why})" for c, why in sorted(result.skipped.items())))
    print(f"rapport qualité -> {result.quality_path}")
