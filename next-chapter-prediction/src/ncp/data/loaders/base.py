"""Registre des chargeurs et detection de format."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from ncp.config.schema import DatasetConfig
from ncp.data.schema import RawRecord

#: Signature d'un chargeur.
Loader = Callable[[Path, DatasetConfig], Iterator[RawRecord]]


class LoaderError(ValueError):
    """Format inconnu, chemin illisible ou dataset vide."""


@dataclass(frozen=True)
class LoaderSpec:
    name: str
    loader: Loader
    #: Extensions de fichier reconnues par la detection automatique.
    extensions: tuple[str, ...]
    #: Le chargeur attend-il un dossier plutot qu'un fichier ?
    directory: bool
    description: str


_REGISTRY: dict[str, LoaderSpec] = {}


def register_loader(
    name: str,
    *,
    extensions: Sequence[str] = (),
    directory: bool = False,
    description: str = "",
) -> Callable[[Loader], Loader]:
    """Decorateur d'enregistrement d'un chargeur."""

    def decorator(loader: Loader) -> Loader:
        if name in _REGISTRY:
            raise LoaderError(f"Chargeur deja enregistre : {name!r}")
        summary = description
        if not summary and loader.__doc__:
            summary = loader.__doc__.strip().splitlines()[0]
        _REGISTRY[name] = LoaderSpec(
            name=name,
            loader=loader,
            extensions=tuple(ext.lower() for ext in extensions),
            directory=directory,
            description=summary,
        )
        return loader

    return decorator


def available_loaders() -> dict[str, LoaderSpec]:
    """Les chargeurs enregistres, par nom."""
    return dict(_REGISTRY)


def get_loader(name: str) -> LoaderSpec:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise LoaderError(
            f"Format inconnu : {name!r}. Formats disponibles : "
            f"{', '.join(sorted(_REGISTRY)) or '(aucun)'}"
        ) from None


def detect_format(path: Path, config: DatasetConfig) -> str:
    """Devine le nom du chargeur a partir du chemin.

    Pour un dossier, on regarde les extensions des fichiers qu'il contient : un
    dossier de `.md` est traite comme un dossier markdown, un dossier de `.jsonl`
    comme du JSON Lines concatene.
    """
    if path.is_file():
        suffix = path.suffix.lower()
        for spec in _REGISTRY.values():
            if not spec.directory and suffix in spec.extensions:
                return spec.name
        raise LoaderError(
            f"Impossible de deduire le format de {path.name!r} (extension {suffix!r}). "
            "Renseigner `dataset.format` explicitement. Formats disponibles : "
            f"{', '.join(sorted(_REGISTRY))}"
        )

    if path.is_dir():
        counts: dict[str, int] = {}
        for candidate in path.glob(config.glob):
            if candidate.is_file():
                suffix = candidate.suffix.lower()
                counts[suffix] = counts.get(suffix, 0) + 1
        if not counts:
            raise LoaderError(
                f"Aucun fichier dans {path} avec le motif {config.glob!r}. "
                "Verifier `dataset.path` et `dataset.glob`."
            )
        dominant = max(counts, key=lambda suffix: counts[suffix])
        for spec in _REGISTRY.values():
            if spec.directory and dominant in spec.extensions:
                return spec.name
        for spec in _REGISTRY.values():
            if not spec.directory and dominant in spec.extensions:
                return spec.name
        raise LoaderError(
            f"Extension dominante {dominant!r} dans {path} non reconnue. "
            "Renseigner `dataset.format` explicitement."
        )

    raise LoaderError(f"`dataset.path` introuvable : {path}")


def iter_raw_records(config: DatasetConfig) -> Iterator[RawRecord]:
    """Itere sur les enregistrements bruts du dataset decrit par la configuration."""
    path = config.resolved_path()
    if not path.exists():
        raise LoaderError(
            f"`dataset.path` introuvable : {path}. Verifier le chemin dans la configuration."
        )
    name = config.format if config.format != "auto" else detect_format(path, config)
    spec = get_loader(name)

    if spec.directory:
        if not path.is_dir():
            raise LoaderError(f"Le format {name!r} attend un dossier, or {path} est un fichier.")
        yield from spec.loader(path, config)
        return

    if path.is_file():
        yield from spec.loader(path, config)
        return

    files = sorted(
        candidate
        for candidate in path.glob(config.glob)
        if candidate.is_file() and (not spec.extensions or candidate.suffix.lower() in spec.extensions)
    )
    if not files:
        raise LoaderError(
            f"Aucun fichier {name!r} dans {path} avec le motif {config.glob!r}."
        )
    for candidate in files:
        yield from spec.loader(candidate, config)
