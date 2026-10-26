"""
One Piece — ingestion bronze + silver depuis le wiki Fandom anglais.

Bronze : wikitexte brut de chaque chapitre, archivé tel quel (JSONL).
Silver : un .md par chapitre, front-matter YAML + résumé long.

Usage :
    python -m guess_arc.ingestion --max-chapter 1193                 # run complet
    python -m guess_arc.ingestion --max-chapter 1193 --incremental   # cron hebdo
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from guess_arc import paths

from .parser import parse_chapter
from .silver import write_markdown
from .wiki_client import BATCH, fetch_batch, make_session

# Un chapitre "incomplet" est parfois un faux positif (réponse API tronquée,
# gros espace entre le titre de section et son texte, etc.) : on retélécharge
# la page seule avant de l'archiver comme réellement incomplète.
MAX_RETRIES = 2
RETRY_DELAY = 1.5


def load_state(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))


def load_bronze(path: Path) -> dict[int, dict]:
    archive = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            archive[rec["number"]] = rec
    return archive


def save_bronze(path: Path, archive: dict[int, dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for num in sorted(archive):
            fh.write(json.dumps(archive[num], ensure_ascii=False) + "\n")


def run(max_chapter: int, incremental: bool, delay: float,
        data_dir: Path = paths.DATA_DIR) -> None:
    bronze_dir = paths.bronze_dir(data_dir)
    silver_dir = paths.silver_dir(data_dir)
    state_path = paths.state_path(data_dir)

    bronze_dir.mkdir(parents=True, exist_ok=True)
    state = load_state(state_path) if incremental else {}
    session = make_session()

    bronze_path = bronze_dir / "chapters.jsonl"
    archive = load_bronze(bronze_path)

    changed, skipped, incomplete = 0, 0, []

    for start in range(1, max_chapter + 1, BATCH):
        titles = [
            f"Chapter {n}"
            for n in range(start, min(start + BATCH, max_chapter + 1))
        ]
        print(f"[{start:>4}-{start + len(titles) - 1:>4}] ", end="", flush=True)
        for page in fetch_batch(session, titles):
            num = int(page["title"].replace("Chapter ", ""))
            if page.get("missing"):
                print(f"\n  ! Chapter {num} absent")
                continue
            rev = page["revisions"][0]
            revid = rev["revid"]

            prev = state.get(str(num))
            if incremental and prev and prev.get("revid") == revid and prev.get("complete"):
                skipped += 1
                continue

            wikitext = rev["slots"]["main"]["content"]
            ts = rev["timestamp"]
            ch = parse_chapter(num, wikitext, revid, ts)

            retry = 0
            while not ch.complete and retry < MAX_RETRIES:
                retry += 1
                print(
                    f"\n  ! Chapter {num} incomplet "
                    f"({len(ch.long_summary)} car.), tentative {retry}/{MAX_RETRIES}"
                )
                time.sleep(RETRY_DELAY)
                retry_pages = fetch_batch(session, [f"Chapter {num}"])
                if not retry_pages or retry_pages[0].get("missing"):
                    continue
                retry_rev = retry_pages[0]["revisions"][0]
                wikitext = retry_rev["slots"]["main"]["content"]
                revid = retry_rev["revid"]
                ts = retry_rev["timestamp"]
                ch = parse_chapter(num, wikitext, revid, ts)

            archive[num] = {
                "number": num,
                "revid": revid,
                "timestamp": ts,
                "wikitext": wikitext,
            }
            write_markdown(ch, silver_dir)
            state[str(num)] = {"revid": revid, "complete": ch.complete}
            changed += 1
            if not ch.complete:
                incomplete.append(num)
        print(f"ok  (maj {changed}, inchangés {skipped})")
        time.sleep(delay)

    save_bronze(bronze_path, archive)
    save_state(state_path, state)

    print(f"\nBronze : {bronze_path} ({len(archive)} chapitres)")
    print(f"Silver : {silver_dir}/ ({changed} fichiers écrits, {skipped} inchangés)")
    if incomplete:
        print(f"Incomplets, à repasser : {incomplete}")


def rebuild_silver(data_dir: Path = paths.DATA_DIR) -> int:
    """Régénère toute la silver depuis le bronze archivé, sans appel réseau.

    À lancer après une modification du parseur : c'est la raison d'être du
    bronze (« reparser sans re-scraper »).
    """
    archive = load_bronze(paths.bronze_dir(data_dir) / "chapters.jsonl")
    silver_dir = paths.silver_dir(data_dir)
    for num, rec in sorted(archive.items()):
        ch = parse_chapter(num, rec["wikitext"], rec["revid"], rec["timestamp"])
        write_markdown(ch, silver_dir)
    print(f"Silver : {silver_dir}/ ({len(archive)} fichiers régénérés depuis le bronze)")
    return len(archive)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--max-chapter", type=int, default=1193)
    p.add_argument("--incremental", action="store_true",
                   help="ne retraite que les pages dont la révision a changé")
    p.add_argument("--delay", type=float, default=0.5,
                   help="pause entre lots, en secondes")
    p.add_argument("--data-dir", type=Path, default=paths.DATA_DIR,
                   help="racine des couches bronze/silver (défaut : data/ à la racine du repo)")
    p.add_argument("--rebuild-silver", action="store_true",
                   help="régénère la silver depuis le bronze local, sans réseau")
    args = p.parse_args()
    if args.rebuild_silver:
        rebuild_silver(args.data_dir)
        return
    run(args.max_chapter, args.incremental, args.delay, args.data_dir)


if __name__ == "__main__":
    main()
