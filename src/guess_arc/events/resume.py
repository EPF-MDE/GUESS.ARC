"""Reprise du passage complet : quels chapitres appeler, lesquels garder.

Un chapitre est envoyé au modèle sauf si sa sortie porte déjà l'origine `llm`,
avec les mêmes versions de l'extracteur (modèle, prompt, schéma, taxonomie,
entités ; voir versions.extractor_versions) et
- la même `revision_id` de la silver ;
- ou une révision différente, si la version est gelée.

Un changement de version impose donc de ré-extraire tous les chapitres, gel ou
non (ADR 0002). Un chapitre incomplet (`complete: false`) n'est pas envoyé : il
le sera à un passage suivant, une fois complet.

Geler une version, c'est écrire ses versions dans data/event/frozen.json
(`freeze`) : une fois la vérité terrain validée, les compléments du wiki ne
la font plus bouger. La version gelée ne vaut que tant que les versions
courantes sont celles du fichier.
"""

from __future__ import annotations

import json
from pathlib import Path

from guess_arc import paths

from .outputs import read_meta
from .silver import SilverChapter
from .versions import extractor_versions


def freeze(data_dir: Path, model: str) -> Path:
    """Gèle la version courante de l'extracteur pour `model`."""
    path = paths.event_frozen_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(extractor_versions(model), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return path


def is_frozen(data_dir: Path, model: str) -> bool:
    """Les versions courantes de l'extracteur, pour `model`, sont celles gelées."""
    path = paths.event_frozen_path(data_dir)
    if not path.exists():
        return False
    return json.loads(path.read_text(encoding="utf-8")) == extractor_versions(model)


def is_up_to_date(ch: SilverChapter, out_dir: Path, model: str, frozen: bool) -> bool:
    """La sortie du chapitre est à garder : pas d'appel au modèle."""
    meta = read_meta(out_dir, ch.number)
    if meta is None or "llm" not in meta["origins"]:
        return False
    if any(meta.get(key) != value for key, value in extractor_versions(model).items()):
        return False
    return frozen or meta["revision_id"] == ch.revision_id
