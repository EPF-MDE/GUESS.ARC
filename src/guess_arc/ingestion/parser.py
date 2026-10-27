"""Parsing déterministe du wikitexte d'une page de chapitre."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Une section s'arrête au prochain titre de niveau égal ou supérieur au sien.
# - Un sous-titre plus profond (===Grand Line-New World===, ===Day 1===, ex.
#   chapitre 590) est avalé comme contenu de ==Long Summary==.
# - ===Chapter Notes=== s'arrête sur ===Characters===, sa sœur dans
#   ==Quick References== : sans cela la table des personnages finissait dans
#   les notes.
# ﻿ : un BOM traîne dans certains titres (===﻿Chapter Notes===, ch. 46).
HEADING_RE = r"^(=+)[\s﻿]*{}\s*=+[ \t]*$"
CHAR_LINE_RE = re.compile(r"^\*\s*\[\[([^\]|]+?)(?:\|[^\]]*)?\]\]\s*(.*)$", re.M)
GROUP_RE = re.compile(r"^;\s*\[\[([^\]|]+?)(?:\|[^\]]*)?\]\]", re.M)
ARC_RE = re.compile(r"\{\{\s*([A-Za-z0-9 '’\-]+ Arc)\s*\}\}")
LINK_RE = re.compile(r"\[\[(?:[^\]|]+\|)?([^\]|]+)\]\]")
# Les chapitres récents annotent ''(cover)'' ; les anciens écrivent (cover).
ANNOT_RE = re.compile(r"(?:'')?\(([^)]*)\)(?:'')?")


def section(wikitext: str, heading: str) -> str:
    m = re.search(HEADING_RE.format(re.escape(heading)), wikitext, re.M | re.I)
    if not m:
        return ""
    level = len(m.group(1))
    end = re.compile(rf"^={{1,{level}}}[^=]", re.M).search(wikitext, m.end())
    return wikitext[m.end():end.start() if end else len(wikitext)].strip()


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
    # Sous-titres internes (===Grand Line-New World===) -> texte brut, gardé
    # comme ligne de titre plutôt que jeté ou laissé en wikitexte.
    text = re.sub(r"^=+\s*(.*?)\s*=+$", r"\1", text, flags=re.M)
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
