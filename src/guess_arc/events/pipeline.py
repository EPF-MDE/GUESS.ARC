"""
One Piece — extraction des événements, de la silver vers data/event/.

Pour l'instant, l'appel au modèle n'est pas livré : `--dry-run` écrit, pour
chaque chapitre, data/event/in/events_NNNN.md (le prompt utilisateur exact) et
data/event/out/events_NNNN.json (les événements d'origine `wiki`, déduits des
apparitions), sans appeler le modèle. Les événements `wiki` d'une plage sont
calculés sur toute la silver qui la précède.

Usage :
    python -m guess_arc.events --dry-run                       # tous les chapitres
    python -m guess_arc.events --dry-run --from 90 --to 100    # une plage

Le préparsing écrit aussi data/event/future_leak_candidates.json, la liste des
passages qui parlent de la suite de l'histoire. Ils ne sont retirés du texte
qu'une fois marqués `remove` dans review/future_leaks.json (voir future_leaks).
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

from guess_arc import paths

from .future_leaks import load_review, stale_decisions, write_candidates
from .entities import Entities, EntitySelector
from .inputs import estimated_tokens, render_user_prompt, write_input
from .outputs import write_output
from .preparse import preparse
from .silver import read_chapter
from .wiki import wiki_events

SILVER_NAME_RE = re.compile(r"^chapter_(\d+)\.md$")


def silver_chapters(silver_dir: Path, first: int | None, last: int | None) -> list[Path]:
    """Fichiers silver de la plage [first, last], dans l'ordre des chapitres."""
    selected = []
    for path in silver_dir.glob("chapter_*.md"):
        match = SILVER_NAME_RE.match(path.name)
        if not match:
            continue
        num = int(match.group(1))
        if (first is None or num >= first) and (last is None or num <= last):
            selected.append((num, path))
    return [path for _, path in sorted(selected)]


def run(data_dir: Path = paths.DATA_DIR, first: int | None = None,
        last: int | None = None, dry_run: bool = False,
        review_path: Path = paths.FUTURE_LEAK_REVIEW_PATH) -> int:
    if not dry_run:
        raise NotImplementedError("extraction llm pas encore disponible : utiliser --dry-run")
    in_dir, out_dir = paths.event_in_dir(data_dir), paths.event_out_dir(data_dir)
    # Toute la silver jusqu'à la fin de la plage : les événements `wiki` dépendent
    # des chapitres qui précèdent.
    history = [read_chapter(path)
               for path in silver_chapters(paths.silver_dir(data_dir), None, last)]
    wiki_by_chapter = wiki_events(history)
    selected = [ch for ch in history if first is None or ch.number >= first]
    decisions = load_review(review_path)
    entity_dir = paths.entities_dir(data_dir)
    entities = Entities.load(entity_dir)
    if not entities.characters:
        print(f"attention : aucune fiche de personnage dans {entity_dir}/, "
              "seuls les noms de la table des personnages sont envoyés")
    # Le filtre de temps lit aussi les chapitres qui précèdent la plage.
    selector = EntitySelector(entities)
    removed, candidates, chapters, sizes = Counter(), [], set(), []
    for ch in history:
        selector.observe(ch)
        if first is not None and ch.number < first:
            continue
        p = preparse(ch, decisions)
        block = selector.select(ch, p.text)
        chapters.add(p.number)
        write_input(p, block, in_dir)
        write_output(ch, wiki_by_chapter[ch.number], out_dir)
        candidates.extend(p.leak_candidates)
        removed.update(p.flags)
        sizes.append(estimated_tokens(render_user_prompt(p, block)))
    candidates_path = paths.event_leak_candidates_path(data_dir)
    write_candidates(candidates, candidates_path)
    print(f"Entrées : {in_dir}/ ({len(selected)} fichiers écrits)")
    for name, count in removed.items():
        print(f"  {name} : {count}")
    if sizes:
        sizes.sort()
        print(f"  prompt utilisateur, en tokens estimés (4 caractères/token) : "
              f"médiane {sizes[len(sizes) // 2]}, 95e centile "
              f"{sizes[int(len(sizes) * 0.95)]}, max {sizes[-1]}")
    pending = sum(c.decision is None for c in candidates)
    print(f"Fuites du futur : {candidates_path} ({len(candidates)} candidats, "
          f"{pending} à relire dans {review_path})")
    stale = stale_decisions(decisions, candidates, chapters)
    if stale:
        print(f"  attention : {stale} décisions ne désignent plus aucun passage "
              "(texte de la silver modifié), à relire")
    counts = Counter(e.type for ch in selected for e in wiki_by_chapter[ch.number])
    print(f"Événements wiki : {out_dir}/ ({len(selected)} fichiers écrits)")
    for name, count in counts.items():
        print(f"  {name} : {count}")
    return len(selected)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", type=Path, default=paths.DATA_DIR,
                   help="racine des couches silver/event (défaut : data/ à la racine du repo)")
    p.add_argument("--dry-run", action="store_true",
                   help="écrit les fichiers d'entrée et les événements wiki "
                        "sans appeler le modèle")
    p.add_argument("--from", dest="first", type=int, default=None,
                   help="premier chapitre traité (défaut : le premier de la silver)")
    p.add_argument("--to", dest="last", type=int, default=None,
                   help="dernier chapitre traité (défaut : le dernier de la silver)")
    p.add_argument("--leak-review", type=Path, default=paths.FUTURE_LEAK_REVIEW_PATH,
                   help="décisions de relecture des fuites du futur "
                        "(défaut : review/future_leaks.json)")
    args = p.parse_args(argv)
    if not args.dry_run:
        p.error("l'extraction llm n'est pas encore disponible : utiliser --dry-run")
    run(args.data_dir, args.first, args.last, dry_run=True, review_path=args.leak_review)


if __name__ == "__main__":
    main()
