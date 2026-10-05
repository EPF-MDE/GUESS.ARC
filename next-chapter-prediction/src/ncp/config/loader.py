"""Chargement des configurations.

Une configuration finale est la fusion, dans l'ordre :

1. les valeurs par defaut des dataclasses de `ncp.config.schema` ;
2. `configs/default.yaml` (sauf si `use_defaults=False`) ;
3. chaque fichier passe en `--config`, dans l'ordre de la ligne de commande ;
4. les surcharges ponctuelles `--set cle.pointee=valeur`.

Ce decoupage permet de garder le chemin du dataset dans un fichier local non
versionne et de ne commiter que les configurations d'experience.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from ncp.config.schema import Config, ConfigError
from ncp.utils.io import dump_json, dump_yaml, load_structured_file

#: Nom du fichier de configuration par defaut, cherche a la racine du projet.
DEFAULT_CONFIG_NAME = "configs/default.yaml"


def project_root(start: Path | None = None) -> Path:
    """Remonte depuis `start` jusqu'au dossier contenant `pyproject.toml`.

    Permet de lancer la CLI depuis n'importe quel sous-dossier. Si rien n'est
    trouve, retourne le repertoire de depart.
    """
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").exists():
            return candidate
    return current


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Fusionne `override` dans `base` recursivement, sans muter les entrees.

    Les dictionnaires sont fusionnes cle par cle ; toute autre valeur (liste
    incluse) est remplacee, pour qu'une liste declaree dans une configuration
    d'experience ecrase bien celle des defauts au lieu de s'y ajouter.
    """
    merged = dict(base)
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(existing, Mapping) and isinstance(value, Mapping):
            merged[key] = deep_merge(existing, value)
        else:
            merged[key] = value
    return merged


def _coerce_scalar(raw: str) -> Any:
    """Convertit une valeur de ligne de commande vers un type Python.

    Essaie JSON d'abord (gere `3`, `0.5`, `true`, `null`, `[1,2]`, `{"a":1}`),
    puis quelques litteraux YAML usuels, et retombe sur la chaine brute.
    """
    text = raw.strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass
    lowered = text.lower()
    if lowered in {"true", "yes", "on"}:
        return True
    if lowered in {"false", "no", "off"}:
        return False
    if lowered in {"none", "null", ""}:
        return None
    return text


def parse_override(assignment: str) -> dict[str, Any]:
    """Transforme `"a.b=1"` en `{"a": {"b": 1}}`."""
    if "=" not in assignment:
        raise ConfigError(
            f"Surcharge invalide : {assignment!r}. Format attendu : cle.pointee=valeur"
        )
    dotted, _, raw_value = assignment.partition("=")
    keys = [part for part in dotted.strip().split(".") if part]
    if not keys:
        raise ConfigError(f"Surcharge invalide : {assignment!r}. La cle est vide.")
    nested: Any = _coerce_scalar(raw_value)
    for key in reversed(keys):
        nested = {key: nested}
    return nested


def apply_overrides(data: Mapping[str, Any], assignments: Iterable[str]) -> dict[str, Any]:
    """Applique une suite de surcharges `cle.pointee=valeur`."""
    merged = dict(data)
    for assignment in assignments:
        merged = deep_merge(merged, parse_override(assignment))
    return merged


def load_config_dict(
    paths: Sequence[str | Path] = (),
    overrides: Sequence[str] = (),
    *,
    use_defaults: bool = True,
    root: Path | None = None,
) -> dict[str, Any]:
    """Construit le dictionnaire de configuration fusionne, sans le valider."""
    base = project_root(root)
    data: dict[str, Any] = {}
    if use_defaults:
        default_path = base / DEFAULT_CONFIG_NAME
        if default_path.exists():
            data = deep_merge(data, load_structured_file(default_path))
    for path in paths:
        candidate = Path(path)
        if not candidate.is_absolute() and not candidate.exists():
            candidate = base / candidate
        data = deep_merge(data, load_structured_file(candidate))
    return apply_overrides(data, overrides)


def load_config(
    paths: Sequence[str | Path] = (),
    overrides: Sequence[str] = (),
    *,
    use_defaults: bool = True,
    root: Path | None = None,
    validate: bool = True,
) -> Config:
    """Charge, fusionne, instancie et valide la configuration."""
    data = load_config_dict(paths, overrides, use_defaults=use_defaults, root=root)
    config = Config.from_dict(data)
    if validate:
        config.validate()
    return config


def save_config(config: Config, path: str | Path) -> Path:
    """Archive la configuration a cote des resultats d'un run."""
    target = Path(path)
    if target.suffix.lower() == ".json":
        return dump_json(config.to_dict(), target)
    return dump_yaml(config.to_dict(), target)
