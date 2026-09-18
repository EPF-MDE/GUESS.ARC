"""Résolution de noms canoniques via les redirections du wiki Fandom One Piece.

Le clustering par embedding sémantique (cf. 03_cluster_taxonomy.py) chaîne à
tort des noms propres One Piece qui n'ont rien à voir entre eux : le modèle
d'embedding, hors-vocabulaire sur ces noms, capture une ressemblance de
surface/phonétique et non leur sens (ex. "Onigashima"/"Earth" ont une
similarité cosinus de 0.79 alors qu'ils sont sans rapport, quand "the Grand
Line"/"Laugh Tale" — fortement liés dans l'histoire — n'en ont que 0.21).
Aucun réglage de seuil ne corrige cet effet de chaînage.

Le wiki Fandom, lui, encode une vérité terrain gratuite et fiable : chaque
alias/surnom d'un personnage, lieu ou objet est une page de redirection vers
sa page canonique, maintenue par les contributeurs. On interroge donc
`action=query&redirects=1` (même API que `onepiece_ingest.py`) pour résoudre
chaque candidat vers son nom canonique wiki avant de clusteriser : le
clustering par embedding ne sert plus que de repli pour ce que le wiki ne
couvre pas.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests

API = "https://onepiece.fandom.com/api.php"
UA = "OnePieceTagPrediction/0.1 (projet academique; contact: morotti.maxime@gmail.com)"
BATCH = 50  # limite MediaWiki pour un utilisateur anonyme (cf. onepiece_ingest.py)


class WikiGazetteer:
    """Résout une liste de termes vers leur nom canonique de page wiki.

    Le cache est persisté sur disque (`cache_path`) : un terme déjà résolu
    (ou confirmé absent du wiki) lors d'un run précédent n'est jamais
    réinterrogé, ce qui garde les runs suivants rapides et épargne l'API.
    """

    def __init__(self, cache_path: Path, delay: float = 0.3):
        self.cache_path = cache_path
        self.delay = delay
        self.cache: dict[str, str | None] = {}
        if cache_path.exists():
            self.cache = json.loads(cache_path.read_text(encoding="utf-8"))
        self.session = requests.Session()
        self.session.headers["User-Agent"] = UA

    def save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(self.cache, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _fetch_batch(self, titles: list[str]) -> dict[str, str | None]:
        params = {
            "action": "query",
            "titles": "|".join(titles),
            "redirects": "1",
            "format": "json",
            "formatversion": "2",
        }
        data = None
        for attempt in range(4):
            try:
                r = self.session.get(API, params=params, timeout=30)
                r.raise_for_status()
                data = r.json()["query"]
                break
            except Exception as exc:  # noqa: BLE001
                if attempt == 3:
                    print(f"[gazetteer] échec définitif sur ce lot ({exc!r}), laissé non résolu.")
                    return {t: None for t in titles}
                wait = 2 ** attempt
                print(f"[gazetteer] retry dans {wait}s ({exc})")
                time.sleep(wait)

        # Applique d'abord la normalisation MediaWiki (casse/espaces), puis la
        # redirection, dans l'ordre où l'API les documente.
        resolved = {t: t for t in titles}
        for entry in data.get("normalized", []):
            for t in resolved:
                if resolved[t] == entry["from"]:
                    resolved[t] = entry["to"]
        for entry in data.get("redirects", []):
            for t in resolved:
                if resolved[t] == entry["from"]:
                    resolved[t] = entry["to"]

        missing_titles = {p["title"] for p in data.get("pages", []) if p.get("missing")}
        return {t: (None if resolved[t] in missing_titles else resolved[t]) for t in titles}

    def resolve_many(self, terms: list[str]) -> dict[str, str | None]:
        """Résout une liste de termes (avec cache). Ne réinterroge que les inconnus.

        Retourne {terme: nom_canonique_wiki | None}. None = absent du wiki,
        laissé au clustering par embedding en repli. Les termes contenant "|"
        (séparateur de lot MediaWiki) sont ignorés sans requête.
        """
        unique = sorted({t for t in terms if t and t.strip() and "|" not in t})
        to_query = [t for t in unique if t not in self.cache]

        for start in range(0, len(to_query), BATCH):
            batch = to_query[start : start + BATCH]
            resolved = self._fetch_batch(batch)
            self.cache.update(resolved)
            if start + BATCH < len(to_query):
                time.sleep(self.delay)

        if to_query:
            self.save()

        return {t: self.cache.get(t) for t in unique}
