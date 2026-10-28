"""Écriture de data/event/out/events_NNNN.json : les événements d'un chapitre.

    {"meta": {...}, "events": [{"id": …, "origin": …, "type": …, …}, …]}

Les deux origines y sont fusionnées : d'abord les événements `wiki`, puis ceux
du modèle (`llm`), dédoublonnés et munis de leurs `checks` (voir checks), avec
les noms que le modèle n'a pas trouvés dans la liste (`unlisted_entities`) et
leur contrôle (`unlisted_checks`). `--dry-run` n'écrit que l'origine `wiki`, et laisse
intacte une sortie qui porte déjà l'origine `llm`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .checks import ChapterChecks, deduplicated
from .extraction import Extraction
from .silver import SilverChapter
from .versions import (CHECKS_VERSION, ENTITIES_VERSION, PROMPT_VERSION, SCHEMA_VERSION,
                       TAXONOMY_VERSION)
from .wiki import WikiEvent


def event_id(chapter: int, origin: str, type_: str, participants: list[str]) -> str:
    """Stable d'une exécution à l'autre : un événement par (type, participants) et par chapitre."""
    key = json.dumps(sorted(participants), ensure_ascii=False)
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
    return f"{chapter:04d}-{origin}-{type_}-{digest}"


def wiki_record(chapter: int, e: WikiEvent) -> dict:
    return {
        "id": event_id(chapter, "wiki", e.type, [e.name]),
        "origin": "wiki",
        "type": e.type,
        "description": e.description,
        "participants": [{"name": e.name, "role": e.role}],
        "location": "",
        "status": "single",
        "in_flashback": e.in_flashback,
        "evidence": "",
        "source": "characters",
    }


def llm_records(chapter: int, events: list[dict], checks: ChapterChecks) -> list[dict]:
    """Événements du modèle, dans l'ordre de la réponse.

    Deux événements de même type et mêmes participants, mais pas identiques (la
    règle de granularité l'interdit ; seules les copies exactes sont retirées),
    reçoivent `-2`, `-3`… pour que l'`id` reste unique.
    """
    records, seen = [], {}
    for e in events:
        names = [p["name"] for p in e["participants"]]
        base = event_id(chapter, "llm", e["type"], names)
        seen[base] = seen.get(base, 0) + 1
        records.append({
            "id": base if seen[base] == 1 else f"{base}-{seen[base]}",
            "origin": "llm",
            "type": e["type"],
            "description": e["description"],
            "participants": e["participants"],
            "location": e["location"],
            "status": e["status"],
            "in_flashback": e["in_flashback"],
            "evidence": e["evidence"],
            "source": e["source"],
            "checks": checks.event_checks(e),
        })
    return records


def render_output(ch: SilverChapter, wiki: list[WikiEvent],
                  llm: Extraction | None = None, checks: ChapterChecks | None = None) -> str:
    """`checks` accompagne toujours `llm` : les contrôles du chapitre."""
    events = [wiki_record(ch.number, e) for e in wiki]
    meta = {"chapter": ch.number, "revision_id": ch.revision_id,
            "taxonomy_version": TAXONOMY_VERSION, "entities_version": ENTITIES_VERSION,
            # Origines déjà passées sur ce fichier : tant que `llm` manque, le
            # chapitre reste à extraire par le modèle.
            "origins": ["wiki"]}
    document = {"meta": meta, "events": events}
    if llm is not None:
        unique, duplicates = deduplicated(llm.document["events"])
        meta |= {"model": llm.model, "prompt_version": PROMPT_VERSION,
                 "schema_version": SCHEMA_VERSION, "checks_version": CHECKS_VERSION,
                 "attempts": llm.attempts,
                 "duplicates_removed": duplicates, "origins": ["wiki", "llm"]}
        events.extend(llm_records(ch.number, unique, checks))
        unlisted = llm.document["unlisted_entities"]
        document["unlisted_entities"] = unlisted
        document["unlisted_checks"] = checks.unlisted_checks(unlisted)
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def output_path(out_dir: Path, chapter: int) -> Path:
    return out_dir / f"events_{chapter:04d}.json"


def has_llm_events(out_dir: Path, chapter: int) -> bool:
    """La sortie existante porte déjà l'origine `llm` (un `--dry-run` ne l'écrase pas)."""
    path = output_path(out_dir, chapter)
    if not path.exists():
        return False
    return "llm" in json.loads(path.read_text(encoding="utf-8"))["meta"]["origins"]


def write_output(ch: SilverChapter, wiki: list[WikiEvent], out_dir: Path,
                 llm: Extraction | None = None, checks: ChapterChecks | None = None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = output_path(out_dir, ch.number)
    path.write_text(render_output(ch, wiki, llm, checks), encoding="utf-8")
    return path
