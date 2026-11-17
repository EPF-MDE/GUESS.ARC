"""Extraction des Entities depuis le bronze, jusqu'à Registry(t) dans la gold.

    extraction -> fonction pure `extract_entities(chapters, reference)`, seul point d'entrée
    pipeline   -> lecture du bronze, écriture de la gold (dont le contexte de chaque
                  chapitre pour l'extracteur d'Events), CLI
"""

from .extraction import (ChapterContext, Disguise, DisguiseCandidate, Extraction, Participant,
                         Reference, RegistryRow, Scene, extract_entities)

__all__ = ["ChapterContext", "Disguise", "DisguiseCandidate", "Extraction", "Participant",
           "Reference", "RegistryRow", "Scene", "extract_entities"]
