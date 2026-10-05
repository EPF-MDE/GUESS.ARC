"""Modele de donnees interne.

Le reste du projet ne manipule que ces trois objets, jamais le format source.
C'est ce qui permet de brancher un nouveau dataset sans toucher au pipeline :
seul un chargeur est a ecrire.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

#: Un enregistrement brut tel que sorti d'un chargeur, avant mapping des champs.
RawRecord = dict[str, Any]


@dataclass(frozen=True)
class ChapterRecord:
    """Un chapitre : son rang dans le livre et son resume."""

    book_id: str
    index: int
    summary: str
    title: str | None = None
    #: Tout ce que la source portait en plus et qu'on a choisi de garder.
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> tuple[str, int]:
        return (self.book_id, self.index)

    def with_summary(self, summary: str) -> ChapterRecord:
        """Copie du chapitre avec un resume remplace (sortie du preprocessing)."""
        return replace(self, summary=summary)

    def to_dict(self) -> dict[str, Any]:
        return {
            "book_id": self.book_id,
            "index": self.index,
            "title": self.title,
            "summary": self.summary,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ChapterRecord:
        return cls(
            book_id=str(data["book_id"]),
            index=int(data["index"]),
            summary=str(data.get("summary") or ""),
            title=data.get("title"),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True)
class Book:
    """Les chapitres d'un meme livre, tries par `index` croissant."""

    book_id: str
    chapters: tuple[ChapterRecord, ...]

    def __len__(self) -> int:
        return len(self.chapters)

    def __iter__(self) -> Iterator[ChapterRecord]:
        return iter(self.chapters)

    def __getitem__(self, position: int) -> ChapterRecord:
        return self.chapters[position]

    @property
    def indices(self) -> tuple[int, ...]:
        return tuple(chapter.index for chapter in self.chapters)


@dataclass(frozen=True)
class Corpus:
    """L'ensemble des livres charges."""

    books: tuple[Book, ...]

    @classmethod
    def from_records(cls, records: Iterable[ChapterRecord]) -> Corpus:
        """Regroupe des chapitres par livre et les trie par index.

        En cas d'index duplique dans un meme livre, le dernier enregistrement lu
        gagne : un dataset reconstruit par-dessus un ancien reste utilisable.
        """
        grouped: dict[str, dict[int, ChapterRecord]] = {}
        for record in records:
            grouped.setdefault(record.book_id, {})[record.index] = record
        books = tuple(
            Book(
                book_id=book_id,
                chapters=tuple(by_index[index] for index in sorted(by_index)),
            )
            for book_id, by_index in sorted(grouped.items())
        )
        return cls(books=books)

    def __len__(self) -> int:
        return len(self.books)

    def __iter__(self) -> Iterator[Book]:
        return iter(self.books)

    @property
    def chapters(self) -> tuple[ChapterRecord, ...]:
        return tuple(chapter for book in self.books for chapter in book)

    def book(self, book_id: str) -> Book:
        for book in self.books:
            if book.book_id == book_id:
                return book
        raise KeyError(f"Livre inconnu : {book_id!r}")

    def filter_chapters(self, predicate) -> Corpus:
        """Nouveau corpus restreint aux chapitres satisfaisant `predicate`."""
        return Corpus.from_records(chapter for chapter in self.chapters if predicate(chapter))

    def map_chapters(self, transform) -> Corpus:
        """Nouveau corpus ou chaque chapitre est passe dans `transform`.

        `transform` peut retourner `None` pour ecarter un chapitre.
        """
        mapped = (transform(chapter) for chapter in self.chapters)
        return Corpus.from_records(chapter for chapter in mapped if chapter is not None)


def records_to_dicts(records: Sequence[ChapterRecord]) -> list[dict[str, Any]]:
    return [record.to_dict() for record in records]
