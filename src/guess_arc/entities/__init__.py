"""Extraction des Entities depuis le bronze, jusqu'à Registry(t) dans la gold.

    extraction -> fonction pure `extract_entities(chapters, reference)`, seul point d'entrée
    pipeline   -> lecture du bronze, écriture de la gold, CLI
"""

from .extraction import Disguise, DisguiseCandidate, Extraction, Reference, RegistryRow, extract_entities

__all__ = ["Disguise", "DisguiseCandidate", "Extraction", "Reference", "RegistryRow", "extract_entities"]
