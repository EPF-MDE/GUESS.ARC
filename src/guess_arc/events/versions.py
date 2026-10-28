"""Versions notées dans chaque fichier de data/event/.

Changer l'une d'elles impose de relancer tous les chapitres : les entrées
(chapitres 1 à t) et la vérité terrain (t+1) doivent sortir du même extracteur
(ADR 0002).
"""

PROMPT_VERSION = "v1"
SCHEMA_VERSION = "v1"
ENTITIES_VERSION = "v0"
TAXONOMY_VERSION = "v1"
# Règles des contrôles (checks) : elles ne changent pas la réponse du modèle,
# seulement les marques posées dessus.
CHECKS_VERSION = "v1"


def extractor_versions(model: str) -> dict[str, str]:
    """Ce qui fait l'extracteur : tout changement impose de ré-extraire chaque chapitre.

    `CHECKS_VERSION` n'en fait pas partie : les contrôles ne changent pas la
    réponse du modèle.
    """
    return {"model": model, "prompt_version": PROMPT_VERSION,
            "schema_version": SCHEMA_VERSION, "taxonomy_version": TAXONOMY_VERSION,
            "entities_version": ENTITIES_VERSION}
