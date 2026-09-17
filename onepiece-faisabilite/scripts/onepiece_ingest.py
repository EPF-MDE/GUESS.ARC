#!/usr/bin/env python3
"""
One Piece — ingestion bronze + silver depuis le wiki Fandom anglais.

Bronze : wikitexte brut de chaque chapitre, archivé tel quel (JSONL).
Silver : un .md par chapitre, front-matter YAML + résumé long.

Usage :
    python onepiece_ingest.py --max-chapter 1193            # run complet
    python onepiece_ingest.py --max-chapter 1193 --incremental   # cron hebdo

Dépendances : requests, pyyaml
    pip install requests pyyaml

Le contenu Fandom est sous licence CC BY-SA. Usage académique avec attribution.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

import requests

API = "https://onepiece.fandom.com/api.php"
UA = "OnePieceTagPrediction/0.1 (projet academique; contact: morotti.maxime@gmail.com)"
BATCH = 50  # limite MediaWiki pour un utilisateur anonyme

BRONZE = Path("data/bronze")
SILVER = Path("data/silver")
STATE = Path("data/state.json")


# --------------------------------------------------------------------------
# Récupération
# --------------------------------------------------------------------------

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


# --------------------------------------------------------------------------
# Parsing du wikitexte
# --------------------------------------------------------------------------

# S'arrête à la prochaine section de n'importe quel niveau : ===Chapter Notes===
# est suivi de ===Characters===, qu'il ne faut pas avaler.
SECTION_RE = r"==+\s*{}\s*==+(.*?)(?=\n==|\Z)"
CHAR_LINE_RE = re.compile(r"^\*\s*\[\[([^\]|]+?)(?:\|[^\]]*)?\]\]\s*(.*)$", re.M)
GROUP_RE = re.compile(r"^;\s*\[\[([^\]|]+?)(?:\|[^\]]*)?\]\]", re.M)
ARC_RE = re.compile(r"\{\{\s*([A-Za-z0-9 '’\-]+ Arc)\s*\}\}")
LINK_RE = re.compile(r"\[\[(?:[^\]|]+\|)?([^\]|]+)\]\]")
# Les chapitres récents annotent ''(cover)'' ; les anciens écrivent (cover).
ANNOT_RE = re.compile(r"(?:'')?\(([^)]*)\)(?:'')?")


def section(wikitext: str, heading: str) -> str:
    m = re.search(SECTION_RE.format(re.escape(heading)), wikitext, re.S | re.I)
    return m.group(1).strip() if m else ""


def parse_characters(char_section: str) -> list[dict]:
    """
    La section Characters est une CharTable : des groupes ';[[Faction]]'
    suivis de lignes '*[[Personnage]]' parfois annotées ''(cover)'' / ''(flashback)''.
    On parcourt dans l'ordre pour rattacher chaque personnage à sa faction.
    """
    out: list[dict] = []
    seen: set[str] = set()
    current_group = None

    for line in char_section.splitlines():
        line = line.strip()
        g = GROUP_RE.match(line)
        if g:
            current_group = g.group(1).strip()
            continue
        if line.startswith(";"):  # groupe sans lien
            current_group = re.sub(r"[\[\];']", "", line).strip() or current_group
            continue
        c = CHAR_LINE_RE.match(line)
        if not c:
            continue
        name = c.group(1).strip()
        if name in seen:
            continue
        seen.add(name)
        annots = [a.strip().lower() for a in ANNOT_RE.findall(c.group(2))]
        out.append({
            "name": name,
            "faction": current_group,
            # 'on_panel' : présent à l'image dans le présent du récit.
            # cover / flashback / mentioned sont exclus.
            "on_panel": not any(
                k in a for a in annots for k in ("cover", "flashback", "mentioned", "dream")
            ),
            "annotations": annots,
        })
    return out


def strip_markup(text: str) -> str:
    """Wikitexte -> texte lisible, en gardant les noms des liens."""
    text = LINK_RE.sub(r"\1", text)
    text = re.sub(r"\{\{[^}]*\}\}", "", text)
    text = re.sub(r"'''?", "", text)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


@dataclass
class Chapter:
    number: int
    title: str | None = None
    jname: str | None = None
    arc: str | None = None
    revision_id: int | None = None
    revised_at: str | None = None
    characters: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    short_summary: str = ""
    long_summary: str = ""
    complete: bool = False


def parse_chapter(number: int, wikitext: str, revid: int, ts: str) -> Chapter:
    title = re.search(r"\|\s*title\s*=\s*([^\n|}]+)", wikitext)
    jname = re.search(r"\|\s*jname\s*=\s*([^\n|}]+)", wikitext)
    arc = ARC_RE.search(wikitext)

    long_s = strip_markup(section(wikitext, "Long Summary"))
    notes_raw = section(wikitext, "Chapter Notes")
    notes = [
        strip_markup(m.group(1))
        for m in re.finditer(r"^\*+\s*(.+)$", notes_raw, re.M)
    ]

    return Chapter(
        number=number,
        title=title.group(1).strip() if title else None,
        jname=jname.group(1).strip() if jname else None,
        arc=arc.group(1) if arc else None,
        revision_id=revid,
        revised_at=ts,
        characters=parse_characters(section(wikitext, "Characters")),
        notes=notes,
        short_summary=strip_markup(section(wikitext, "Short Summary")),
        long_summary=long_s,
        # Seuil de 300 caractères : en dessous, la page est une ébauche
        # et sera repassée au prochain run du cron.
        complete=len(long_s) >= 300,
    )


# --------------------------------------------------------------------------
# Écriture silver
# --------------------------------------------------------------------------

def yaml_escape(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def write_markdown(ch: Chapter) -> Path:
    SILVER.mkdir(parents=True, exist_ok=True)
    path = SILVER / f"chapter_{ch.number:04d}.md"

    lines = [
        "---",
        f"chapter: {ch.number}",
        f"title: {yaml_escape(ch.title or '')}",
        f"jname: {yaml_escape(ch.jname or '')}",
        f"arc: {yaml_escape(ch.arc or '')}",
        f"revision_id: {ch.revision_id}",
        f"revised_at: {yaml_escape(ch.revised_at or '')}",
        f"complete: {str(ch.complete).lower()}",
        f"character_count: {len(ch.characters)}",
        "characters:",
    ]
    for c in ch.characters:
        lines += [
            f"  - name: {yaml_escape(c['name'])}",
            f"    faction: {yaml_escape(c['faction'] or '')}",
            f"    on_panel: {str(c['on_panel']).lower()}",
        ]
    lines += [
        "source: https://onepiece.fandom.com/wiki/Chapter_%d" % ch.number,
        "license: CC BY-SA",
        "---",
        "",
        f"# Chapter {ch.number} — {ch.title or ''}".rstrip(" —"),
        "",
        "## Short Summary",
        "",
        ch.short_summary or "_(absent)_",
        "",
        "## Long Summary",
        "",
        ch.long_summary or "_(absent)_",
        "",
        "## Chapter Notes",
        "",
    ]
    lines += [f"- {n}" for n in ch.notes] or ["_(absentes)_"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def load_state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2))


def run(max_chapter: int, incremental: bool, delay: float) -> None:
    BRONZE.mkdir(parents=True, exist_ok=True)
    state = load_state() if incremental else {}
    session = requests.Session()
    session.headers["User-Agent"] = UA

    bronze_path = BRONZE / "chapters.jsonl"
    archive = {}
    if bronze_path.exists():
        for line in bronze_path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            archive[rec["number"]] = rec

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
            archive[num] = {
                "number": num,
                "revid": revid,
                "timestamp": rev["timestamp"],
                "wikitext": wikitext,
            }
            ch = parse_chapter(num, wikitext, revid, rev["timestamp"])
            write_markdown(ch)
            state[str(num)] = {"revid": revid, "complete": ch.complete}
            changed += 1
            if not ch.complete:
                incomplete.append(num)
        print(f"ok  (maj {changed}, inchangés {skipped})")
        time.sleep(delay)

    with bronze_path.open("w", encoding="utf-8") as fh:
        for num in sorted(archive):
            fh.write(json.dumps(archive[num], ensure_ascii=False) + "\n")
    save_state(state)

    print(f"\nBronze : {bronze_path} ({len(archive)} chapitres)")
    print(f"Silver : {SILVER}/ ({changed} fichiers écrits, {skipped} inchangés)")
    if incomplete:
        print(f"Incomplets, à repasser : {incomplete}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--max-chapter", type=int, default=1193)
    p.add_argument("--incremental", action="store_true",
                   help="ne retraite que les pages dont la révision a changé")
    p.add_argument("--delay", type=float, default=0.5,
                   help="pause entre lots, en secondes")
    run(**vars(p.parse_args()))


if __name__ == "__main__":
    main()
