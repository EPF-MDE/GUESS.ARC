"""Passage des enregistrements bruts au modele interne.

C'est ici que le projet reste format-agnostique : un chargeur se contente de
produire des dictionnaires, et le mapper decide quel champ source joue le role
de resume, de numero de chapitre, etc. La correspondance vient de la
configuration (`dataset.field_map`) ; a defaut elle est devinee parmi des noms
usuels, et ce qui a ete devine est rapporte a l'utilisateur par `ncp inspect`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from ncp.config.schema import DatasetConfig
from ncp.data.schema import ChapterRecord, RawRecord

#: Noms de champs usuels testes pour chaque champ logique, par ordre de priorite.
CANDIDATE_FIELDS: dict[str, tuple[str, ...]] = {
    "book_id": ("book_id", "book", "series", "series_id", "work", "title_id", "novel_id", "arc"),
    "chapter_index": (
        "chapter_index",
        "chapter_number",
        "chapter",
        "number",
        "index",
        "idx",
        "chapter_id",
        "n",
        "order",
        "position",
    ),
    "title": ("title", "chapter_title", "name", "heading", "subject"),
    "summary": (
        "summary",
        "chapter_summary",
        "text",
        "content",
        "body",
        "abstract",
        "synopsis",
        "resume",
        "description",
    ),
}

#: Champs logiques jamais recopies automatiquement dans `metadata`.
_RESERVED = frozenset({"book_id", "chapter_index", "title", "summary"})


class MappingError(ValueError):
    """Un enregistrement brut ne peut pas etre converti en `ChapterRecord`."""


@dataclass
class ResolvedFieldMap:
    """Correspondance effective, une fois la detection automatique appliquee."""

    book_id: str | None = None
    chapter_index: str | None = None
    title: str | None = None
    summary: str | None = None
    #: Champs logiques dont le nom a ete devine plutot que configure.
    guessed: tuple[str, ...] = ()
    #: Champs source presents mais non utilises.
    unused: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "book_id": self.book_id,
            "chapter_index": self.chapter_index,
            "title": self.title,
            "summary": self.summary,
            "guessed": list(self.guessed),
            "unused": list(self.unused),
        }


def _find_field(available: Sequence[str], candidates: Iterable[str]) -> str | None:
    """Cherche un champ par nom exact, puis insensible a la casse et aux separateurs."""

    def normalize(name: str) -> str:
        return name.strip().lower().replace("-", "_").replace(" ", "_")

    lookup = {normalize(name): name for name in available}
    for candidate in candidates:
        key = normalize(candidate)
        if key in lookup:
            return lookup[key]
    return None


def resolve_field_map(config: DatasetConfig, sample: Mapping[str, Any]) -> ResolvedFieldMap:
    """Determine la correspondance a partir de la configuration et d'un echantillon."""
    available = list(sample.keys())
    configured = config.field_map
    resolved = ResolvedFieldMap()
    guessed: list[str] = []

    for logical in ("book_id", "chapter_index", "title", "summary"):
        declared = getattr(configured, logical)
        if declared:
            if declared not in available:
                raise MappingError(
                    f"`dataset.field_map.{logical}` vaut {declared!r}, absent du dataset. "
                    f"Champs disponibles : {', '.join(sorted(available)) or '(aucun)'}"
                )
            setattr(resolved, logical, declared)
            continue
        found = _find_field(available, CANDIDATE_FIELDS[logical])
        if found:
            setattr(resolved, logical, found)
            guessed.append(logical)

    if resolved.summary is None:
        raise MappingError(
            "Impossible d'identifier le champ contenant le resume. Renseigner "
            "`dataset.field_map.summary`. Champs disponibles : "
            f"{', '.join(sorted(available)) or '(aucun)'}"
        )
    if resolved.chapter_index is None and not config.index_from_order:
        raise MappingError(
            "Impossible d'identifier le numero de chapitre. Renseigner "
            "`dataset.field_map.chapter_index`, ou mettre `dataset.index_from_order: true` "
            "pour numeroter les chapitres dans l'ordre de lecture. Champs disponibles : "
            f"{', '.join(sorted(available)) or '(aucun)'}"
        )

    used = {
        value
        for value in (resolved.book_id, resolved.chapter_index, resolved.title, resolved.summary)
        if value
    }
    resolved.guessed = tuple(guessed)
    resolved.unused = tuple(sorted(name for name in available if name not in used))
    return resolved


def _coerce_index(value: Any, *, source_field: str) -> int:
    """Convertit un numero de chapitre vers un entier, en tolerant "12", "12.0", "ch-12"."""
    if isinstance(value, bool):
        raise MappingError(f"Champ {source_field!r} : un booleen n'est pas un numero de chapitre.")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        raise MappingError(f"Champ {source_field!r} : {value!r} n'est pas un entier.")
    text = str(value).strip()
    try:
        return int(text)
    except ValueError:
        pass
    digits = "".join(char for char in text if char.isdigit())
    if digits:
        return int(digits)
    raise MappingError(
        f"Champ {source_field!r} : impossible de lire un numero de chapitre dans {value!r}."
    )


@dataclass
class RecordMapper:
    """Convertit les enregistrements bruts d'un chargeur en `ChapterRecord`.

    Le mapper est volontairement sans etat visible, hormis le compteur qui sert a
    numeroter les chapitres quand la source ne les numerote pas.
    """

    config: DatasetConfig
    resolved: ResolvedFieldMap
    _counters: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_sample(cls, config: DatasetConfig, sample: Mapping[str, Any]) -> RecordMapper:
        return cls(config=config, resolved=resolve_field_map(config, sample))

    def map_one(self, raw: RawRecord) -> ChapterRecord:
        book_id = self.config.default_book_id
        if self.resolved.book_id:
            value = raw.get(self.resolved.book_id)
            if value not in (None, ""):
                book_id = str(value)

        index_field = self.resolved.chapter_index
        if index_field and raw.get(index_field) not in (None, ""):
            index = _coerce_index(raw[index_field], source_field=index_field)
        elif self.config.index_from_order:
            index = self._counters.get(book_id, 0) + 1
        else:
            raise MappingError(
                f"Enregistrement sans numero de chapitre (champ {index_field!r} vide) et "
                "`dataset.index_from_order` desactive."
            )
        self._counters[book_id] = max(self._counters.get(book_id, 0), index)

        summary = raw.get(self.resolved.summary) if self.resolved.summary else None
        title = raw.get(self.resolved.title) if self.resolved.title else None

        keep = self.config.field_map.metadata
        if keep:
            metadata = {name: raw[name] for name in keep if name in raw}
        else:
            metadata = {
                name: value
                for name, value in raw.items()
                if name not in _RESERVED and name not in self._used_source_fields()
            }

        return ChapterRecord(
            book_id=book_id,
            index=index,
            summary="" if summary is None else str(summary),
            title=None if title in (None, "") else str(title),
            metadata=metadata,
        )

    def map_many(self, raws: Iterable[RawRecord]) -> list[ChapterRecord]:
        return [self.map_one(raw) for raw in raws]

    def _used_source_fields(self) -> set[str]:
        return {
            value
            for value in (
                self.resolved.book_id,
                self.resolved.chapter_index,
                self.resolved.title,
                self.resolved.summary,
            )
            if value
        }
