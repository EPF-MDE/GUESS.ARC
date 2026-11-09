"""Cache des catégories du wiki, hors du seam : seul module de l'extraction qui
touche au réseau.

Le cache est un fichier JSON versionné (reference/wiki_categories.json) :
Canonical name -> catégories visibles de sa page. Une page absente du wiki y
figure avec une liste vide, pour ne pas la redemander. Un nom déjà en cache n'est
jamais redemandé : un second run ne fait aucun appel réseau, et le typage reste
reproductible même si le wiki change.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable
from pathlib import Path

from guess_arc.ingestion.wiki_client import BATCH

Fetch = Callable[[list[str]], dict[str, list[str]]]


def load_category_cache(path: Path) -> dict[str, tuple[str, ...]]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {title: tuple(categories) for title, categories in raw.items()}


def _wiki_fetch() -> Fetch:
    from guess_arc.ingestion.wiki_client import fetch_categories, make_session

    session = make_session()

    def fetch(titles: list[str]) -> dict[str, list[str]]:
        result = fetch_categories(session, titles)
        time.sleep(0.5)  # politesse envers l'API
        return result

    return fetch


def update_category_cache(path: Path, titles: Iterable[str], fetch: Fetch | None = None,
                          batch: int = BATCH) -> int:
    """Ajoute au cache les titres qui n'y sont pas encore, par lots de `batch`.
    Renvoie le nombre de titres demandés au wiki."""
    cache = {title: list(cats) for title, cats in load_category_cache(path).items()}
    missing = sorted(set(titles) - set(cache))
    if not missing:
        return 0
    fetch = fetch or _wiki_fetch()
    for i in range(0, len(missing), batch):
        cache.update(fetch(missing[i:i + batch]))
        # Écrit après chaque lot : un run interrompu garde ce qu'il a déjà récupéré.
        path.write_text(json.dumps(dict(sorted(cache.items())), ensure_ascii=False, indent=1),
                        encoding="utf-8")
    return len(missing)
