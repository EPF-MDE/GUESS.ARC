"""Lecture / écriture des formats structurés utilisés par le projet."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

PathLike = str | Path


def _as_path(path: PathLike) -> Path:
    return path if isinstance(path, Path) else Path(path)


def load_yaml(path: PathLike) -> Any:
    """Charge un fichier YAML. Un fichier vide donne ``{}``."""
    import yaml

    with _as_path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def dump_yaml(data: Any, path: PathLike) -> Path:
    import yaml

    target = _as_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)
    return target


def load_json(path: PathLike) -> Any:
    with _as_path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(data: Any, path: PathLike, *, indent: int = 2) -> Path:
    target = _as_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=indent, default=str)
        handle.write("\n")
    return target


def load_jsonl(path: PathLike) -> Iterator[dict[str, Any]]:
    """Itère sur un JSON Lines en ignorant les lignes vides."""
    with _as_path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError as exc:  # pragma: no cover - diagnostic
                raise ValueError(f"{path}:{line_number} n'est pas du JSON valide") from exc


def dump_jsonl(rows: Iterable[Any], path: PathLike) -> Path:
    target = _as_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str))
            handle.write("\n")
    return target


def load_structured_file(path: PathLike) -> Any:
    """Charge un YAML ou un JSON en se fiant à l'extension."""
    target = _as_path(path)
    if not target.exists():
        raise FileNotFoundError(f"Fichier de configuration introuvable : {target}")
    suffix = target.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        return load_yaml(target)
    if suffix == ".json":
        return load_json(target)
    raise ValueError(f"Extension non supportée pour une configuration : {target.suffix!r}")
