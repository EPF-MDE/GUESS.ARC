"""Schema de configuration.

Tout est dataclass : la validation reste lisible, et `to_dict` sert a archiver la
configuration exacte d'un run a cote de ses resultats.

Principe directeur : *aucune hypothese sur le format du dataset*. Le chemin, le
format et la correspondance entre les champs source et les champs logiques du
projet sont tous declares dans la configuration.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T", bound="_Base")


class ConfigError(ValueError):
    """Configuration absente, incoherente ou inutilisable."""


_NESTED_TYPES: dict[str, type] = {}


def _nested_type(annotation: Any) -> type[_Base] | None:
    """Resout une annotation de champ vers une sous-configuration connue."""
    if isinstance(annotation, type) and issubclass(annotation, _Base):
        return annotation
    if isinstance(annotation, str):
        resolved = _NESTED_TYPES.get(annotation)
        if resolved is not None:
            return resolved
    return None


@dataclass
class _Base:
    """Base commune : construction depuis un dict, serialisation vers un dict."""

    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any] | None) -> T:
        data = dict(data or {})
        fields = dataclasses.fields(cls)
        names = {f.name for f in fields}
        unknown = sorted(set(data) - names)
        if unknown:
            raise ConfigError(
                f"Cle(s) inconnue(s) pour {cls.__name__} : {', '.join(unknown)}. "
                f"Cles acceptees : {', '.join(sorted(names))}"
            )
        kwargs: dict[str, Any] = {}
        for f in fields:
            if f.name not in data:
                continue
            value = data[f.name]
            nested = _nested_type(f.type)
            if nested is not None and isinstance(value, dict):
                value = nested.from_dict(value)
            kwargs[f.name] = value
        return cls(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def _register(cls: type) -> type:
    _NESTED_TYPES[cls.__name__] = cls
    return cls


@_register
@dataclass
class FieldMap(_Base):
    """Correspondance champ logique -> champ (ou colonne) du dataset source.

    `None` signifie "detecter automatiquement" : le mapper cherche parmi des noms
    usuels (voir `ncp.data.mapping.CANDIDATE_FIELDS`). Renseigner la valeur
    explicitement des que le format reel du dataset est connu.
    """

    book_id: str | None = None
    chapter_index: str | None = None
    title: str | None = None
    summary: str | None = None
    #: Champs source conserves tels quels dans `ChapterRecord.metadata`.
    metadata: list[str] = field(default_factory=list)


@_register
@dataclass
class DatasetConfig(_Base):
    """Ou sont les donnees, et comment les lire."""

    #: Chemin du dataset, fichier ou dossier. Aucune valeur par defaut : il doit
    #: etre renseigne dans une configuration locale.
    path: str | None = None
    #: `auto` deduit le format du chemin ; sinon un nom de chargeur enregistre
    #: (`jsonl`, `json`, `csv`, `parquet`, `markdown_dir`).
    format: str = "auto"
    #: Motif de fichiers quand `path` est un dossier.
    glob: str = "**/*"
    encoding: str = "utf-8"
    field_map: FieldMap = field(default_factory=FieldMap)
    #: Identifiant de livre utilise quand la source n'en porte aucun.
    default_book_id: str = "book"
    #: Si la source ne numerote pas les chapitres, les numeroter dans l'ordre de lecture.
    index_from_order: bool = False
    #: Options libres transmises au chargeur (delimiteur CSV, cle de colonnes, ...).
    loader_options: dict[str, Any] = field(default_factory=dict)

    def resolved_path(self) -> Path:
        if not self.path:
            raise ConfigError(
                "`dataset.path` n'est pas renseigne. Copier "
                "configs/dataset/local.example.yaml vers configs/dataset/local.yaml, "
                "y mettre le chemin du dataset, puis relancer avec "
                "`--config configs/dataset/local.yaml`."
            )
        return Path(self.path).expanduser()


@_register
@dataclass
class PreprocessConfig(_Base):
    """Nettoyage du texte des resumes."""

    lowercase: bool = False
    collapse_whitespace: bool = True
    strip_markup: bool = True
    strip_citations: bool = True
    unicode_normalize: str | None = "NFKC"
    #: Expressions regulieres supprimees du texte, appliquees dans l'ordre.
    drop_patterns: list[str] = field(default_factory=list)
    #: Tronque le resume a N caracteres (0 = pas de troncature).
    max_chars: int = 0
    #: Ecarte les chapitres dont le resume nettoye est plus court que N caracteres.
    min_chars: int = 0


@_register
@dataclass
class ForecastingConfig(_Base):
    """Construction des exemples "historique -> chapitre suivant"."""

    #: Nombre de chapitres d'historique. 0 = tout l'historique disponible.
    history_size: int = 5
    #: Historique minimal exige pour produire un exemple.
    min_history: int = 1
    #: Pas de la fenetre glissante.
    stride: int = 1
    #: Horizon de prediction : 1 = chapitre suivant immediat.
    horizon: int = 1
    #: Fractions du decoupage (train, validation, test).
    split_ratios: tuple[float, float, float] = (0.8, 0.1, 0.1)
    #: `chronological` decoupe chaque livre dans l'ordre (pas de fuite du futur) ;
    #: `by_book` isole des livres entiers dans chaque split.
    split_strategy: str = "chronological"
    #: Exige que l'historique soit fait de chapitres consecutifs.
    require_contiguous: bool = False


@_register
@dataclass
class AnnotationConfig(_Base):
    """Extraction des entites, evenements et relations."""

    #: Annotateurs appliques, parmi `entities`, `events`, `relations`.
    annotators: list[str] = field(default_factory=lambda: ["entities", "events", "relations"])
    #: `auto` utilise spaCy s'il est installe, sinon repli sur `regex`.
    entity_backend: str = "auto"
    spacy_model: str = "en_core_web_sm"
    #: Types d'entites retenus (liste vide = tous).
    entity_labels: list[str] = field(default_factory=lambda: ["PERSON", "ORG", "GPE", "LOC"])
    #: Lexique d'evenements : type d'evenement -> mots declencheurs.
    #: Vide = charge le lexique par defaut livre avec le paquet.
    event_lexicon: dict[str, list[str]] = field(default_factory=dict)
    event_lexicon_path: str | None = None
    #: Fenetre de co-occurrence pour les relations : `sentence` ou `chapter`.
    relation_window: str = "sentence"
    min_entity_chars: int = 3
    max_entities_per_chapter: int = 50


@_register
@dataclass
class RepresentationConfig(_Base):
    """Comment un exemple devient des features.

    Les cinq valeurs de `name` correspondent aux cinq approches comparees par le
    projet, du texte brut au graphe narratif.
    """

    #: `text`, `text_entities`, `text_events`, `text_full` ou `graph`.
    name: str = "text"
    #: Vectoriseur : `tfidf` (aucun telechargement) ou `sentence_transformer`.
    encoder: str = "tfidf"
    sentence_transformer_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    max_features: int = 20000
    ngram_range: tuple[int, int] = (1, 2)
    #: Poids decroissant des chapitres anciens de l'historique (1.0 = aucun effet).
    recency_decay: float = 1.0
    #: Options libres propres a la variante.
    options: dict[str, Any] = field(default_factory=dict)


@_register
@dataclass
class ModelConfig(_Base):
    """Modele de prediction."""

    #: Nom enregistre : `persistence`, `frequency`, `retrieval`, ...
    name: str = "persistence"
    #: Cible predite : `events`, `entities` ou `both`.
    target: str = "events"
    top_k: int = 10
    #: Hyperparametres transmis au constructeur du modele.
    params: dict[str, Any] = field(default_factory=dict)
    #: Generation d'un resume plausible (desactivee : necessite l'extra `dl`).
    generate_summary: bool = False


@_register
@dataclass
class EvaluationConfig(_Base):
    """Metriques et rapports."""

    metrics: list[str] = field(default_factory=lambda: ["precision", "recall", "f1", "jaccard"])
    #: Seuils k pour precision@k / recall@k.
    k_values: list[int] = field(default_factory=lambda: [1, 5, 10])
    #: Poids par categorie pour le score agrege (vide = poids uniformes).
    category_weights: dict[str, float] = field(default_factory=dict)
    save_predictions: bool = True
    make_plots: bool = False


@_register
@dataclass
class PathsConfig(_Base):
    """Arborescence de sortie. Les chemins relatifs partent du repertoire courant."""

    data_dir: str = "data"
    interim_dir: str = "data/interim"
    processed_dir: str = "data/processed"
    experiments_dir: str = "experiments"
    checkpoints_dir: str = "checkpoints"


@_register
@dataclass
class ExperimentConfig(_Base):
    """Identite d'un run."""

    name: str = "default"
    seed: int = 13
    notes: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class Config(_Base):
    """Configuration complete d'un run."""

    experiment: ExperimentConfig = field(default_factory=ExperimentConfig)
    dataset: DatasetConfig = field(default_factory=DatasetConfig)
    preprocess: PreprocessConfig = field(default_factory=PreprocessConfig)
    forecasting: ForecastingConfig = field(default_factory=ForecastingConfig)
    annotation: AnnotationConfig = field(default_factory=AnnotationConfig)
    representation: RepresentationConfig = field(default_factory=RepresentationConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    evaluation: EvaluationConfig = field(default_factory=EvaluationConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)

    def validate(self) -> Config:
        """Verifie les invariants independants des donnees. Retourne `self`."""
        if not self.dataset.field_map.book_id and not self.dataset.default_book_id:
            raise ConfigError(
                "`dataset.default_book_id` doit etre renseigne (ou "
                "`dataset.field_map.book_id` declare) : sans l'un des deux, "
                "`book_id` serait indefini pour chaque chapitre."
            )
        fc = self.forecasting
        if fc.history_size < 0:
            raise ConfigError("`forecasting.history_size` doit etre >= 0 (0 = tout l'historique).")
        if fc.min_history < 1:
            raise ConfigError("`forecasting.min_history` doit etre >= 1.")
        if fc.history_size and fc.min_history > fc.history_size:
            raise ConfigError(
                "`forecasting.min_history` ne peut pas depasser `forecasting.history_size`."
            )
        if fc.stride < 1:
            raise ConfigError("`forecasting.stride` doit etre >= 1.")
        if fc.horizon < 1:
            raise ConfigError("`forecasting.horizon` doit etre >= 1.")
        if fc.split_strategy not in {"chronological", "by_book"}:
            raise ConfigError(
                "`forecasting.split_strategy` doit valoir chronological ou by_book "
                f"(recu {fc.split_strategy!r})."
            )
        ratios = tuple(fc.split_ratios)
        if len(ratios) != 3:
            raise ConfigError("`forecasting.split_ratios` doit contenir exactement 3 valeurs.")
        if any(r < 0 for r in ratios):
            raise ConfigError("`forecasting.split_ratios` ne peut pas contenir de valeur negative.")
        total = float(sum(ratios))
        if abs(total - 1.0) > 1e-6:
            raise ConfigError(f"`forecasting.split_ratios` doit sommer a 1.0 (recu {total}).")
        if self.model.top_k < 1:
            raise ConfigError("`model.top_k` doit etre >= 1.")
        if self.model.target not in {"events", "entities", "both"}:
            raise ConfigError(
                "`model.target` doit valoir events, entities ou both "
                f"(recu {self.model.target!r})."
            )
        if self.annotation.relation_window not in {"sentence", "chapter"}:
            raise ConfigError(
                "`annotation.relation_window` doit valoir sentence ou chapter "
                f"(recu {self.annotation.relation_window!r})."
            )
        return self
