"""Chargeurs des formats JSON."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ncp.config.schema import DatasetConfig
from ncp.data.loaders.base import LoaderError, register_loader
from ncp.data.schema import RawRecord
from ncp.utils.io import load_json, load_jsonl


@register_loader("jsonl", extensions=(".jsonl", ".ndjson"), description="JSON Lines, un chapitre par ligne")
def load_jsonl_file(path: Path, config: DatasetConfig) -> Iterator[RawRecord]:
    """JSON Lines, un chapitre par ligne."""
    for row in load_jsonl(path):
        if not isinstance(row, dict):
            raise LoaderError(f"{path} : une ligne JSON Lines doit etre un objet, pas {type(row)}.")
        yield row


@register_loader("json", extensions=(".json",), description="JSON : liste d'objets, ou objet contenant une liste")
def load_json_file(path: Path, config: DatasetConfig) -> Iterator[RawRecord]:
    """JSON : liste d'objets, ou objet contenant une liste de chapitres.

    Pour un objet racine, la liste est cherchee sous la cle
    `dataset.loader_options.records_key` si elle est fournie, sinon sous les cles
    usuelles, sinon dans l'unique valeur de type liste.
    """
    data: Any = load_json(path)
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = _extract_list(data, path, config)
    else:
        raise LoaderError(f"{path} : racine JSON inattendue ({type(data)}).")
    for row in rows:
        if not isinstance(row, dict):
            raise LoaderError(f"{path} : element de liste attendu objet, recu {type(row)}.")
        yield row


def _extract_list(data: dict[str, Any], path: Path, config: DatasetConfig) -> list[Any]:
    key = config.loader_options.get("records_key")
    if key:
        if key not in data:
            raise LoaderError(f"{path} : cle {key!r} absente (cles : {', '.join(sorted(data))}).")
        return list(data[key])
    for candidate in ("chapters", "records", "data", "items", "rows", "summaries"):
        if isinstance(data.get(candidate), list):
            return list(data[candidate])
    lists = [value for value in data.values() if isinstance(value, list)]
    if len(lists) == 1:
        return list(lists[0])
    raise LoaderError(
        f"{path} : impossible de localiser la liste de chapitres. Renseigner "
        "`dataset.loader_options.records_key`."
    )
