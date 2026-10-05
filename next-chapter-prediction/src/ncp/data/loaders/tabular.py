"""Chargeurs des formats tabulaires."""

from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path

from ncp.config.schema import DatasetConfig
from ncp.data.loaders.base import LoaderError, register_loader
from ncp.data.schema import RawRecord


@register_loader("csv", extensions=(".csv", ".tsv"), description="CSV / TSV avec ligne d'en-tete")
def load_csv_file(path: Path, config: DatasetConfig) -> Iterator[RawRecord]:
    """CSV / TSV avec ligne d'en-tete.

    Le delimiteur vient de `dataset.loader_options.delimiter` ; a defaut il est
    deduit de l'extension (`.tsv` -> tabulation).
    """
    delimiter = config.loader_options.get("delimiter")
    if not delimiter:
        delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    with path.open("r", encoding=config.encoding, newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if reader.fieldnames is None:
            raise LoaderError(f"{path} : fichier vide ou sans ligne d'en-tete.")
        for row in reader:
            # `csv` rend des chaines vides plutot que None ; on uniformise.
            yield {key: value for key, value in row.items() if key is not None}


@register_loader("parquet", extensions=(".parquet", ".pq"), description="Parquet, via pandas")
def load_parquet_file(path: Path, config: DatasetConfig) -> Iterator[RawRecord]:
    """Parquet, via pandas (necessite pyarrow ou fastparquet)."""
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - pandas est une dependance du coeur
        raise LoaderError("pandas est requis pour lire du Parquet.") from exc
    try:
        frame = pd.read_parquet(path)
    except ImportError as exc:
        raise LoaderError(
            "Lecture Parquet impossible : installer `pyarrow` (pip install pyarrow)."
        ) from exc
    for row in frame.to_dict(orient="records"):
        yield dict(row)
