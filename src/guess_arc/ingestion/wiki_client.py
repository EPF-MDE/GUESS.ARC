"""Accès à l'API MediaWiki du wiki One Piece anglais."""

from __future__ import annotations

import time

import cloudscraper
import requests

API = "https://onepiece.fandom.com/api.php"
UA = "OnePieceTagPrediction/0.1 (projet academique; contact: morotti.maxime@gmail.com)"
BATCH = 50  # limite MediaWiki pour un utilisateur anonyme


def make_session() -> requests.Session:
    session = cloudscraper.create_scraper()
    session.headers["User-Agent"] = UA
    return session


def fetch_batch(session: requests.Session, titles: list[str]) -> list[dict]:
    """Récupère le wikitexte + les métadonnées de révision pour <=50 pages."""
    params = {
        "action": "query",
        "prop": "revisions|info",
        "rvprop": "content|timestamp|ids",
        "rvslots": "main",
        "format": "json",
        "formatversion": "2",
        "titles": "|".join(titles),
    }
    for attempt in range(4):
        try:
            r = session.get(API, params=params, timeout=45)
            r.raise_for_status()
            return r.json()["query"]["pages"]
        except Exception as exc:  # noqa: BLE001
            if attempt == 3:
                raise
            wait = 2 ** attempt
            print(f"  retry dans {wait}s ({exc})")
            time.sleep(wait)
    return []
