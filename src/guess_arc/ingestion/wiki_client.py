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


def _get(session: requests.Session, params: dict) -> dict:
    for attempt in range(4):
        try:
            r = session.get(API, params=params, timeout=45)
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # noqa: BLE001
            if attempt == 3:
                raise
            wait = 2 ** attempt
            print(f"  retry dans {wait}s ({exc})")
            time.sleep(wait)
    return {}


def fetch_categories(session: requests.Session, titles: list[str]) -> dict[str, list[str]]:
    """Catégories visibles (sans le préfixe 'Category:') de <=50 pages.

    Les redirections sont suivies : une page de redirection reçoit les catégories
    de sa cible. Une page absente du wiki reçoit une liste vide.
    """
    params = {
        "action": "query",
        "prop": "categories",
        "clshow": "!hidden",
        "cllimit": "max",
        "redirects": "1",
        "format": "json",
        "formatversion": "2",
        "titles": "|".join(titles),
    }
    by_page: dict[str, set[str]] = {}
    renamed: dict[str, str] = {}
    while True:
        data = _get(session, params)
        query = data.get("query", {})
        for step in query.get("normalized", []) + query.get("redirects", []):
            renamed[step["from"]] = step["to"]
        for page in query.get("pages", []):
            by_page.setdefault(page["title"], set()).update(
                c["title"].split(":", 1)[1] for c in page.get("categories", [])
            )
        if "continue" not in data:
            break
        params = {**params, **data["continue"]}

    out = {}
    for title in titles:
        page = title
        for _ in range(3):  # titre normalisé, puis redirection
            page = renamed.get(page, page)
        out[title] = sorted(by_page.get(page, set()))
    return out


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
