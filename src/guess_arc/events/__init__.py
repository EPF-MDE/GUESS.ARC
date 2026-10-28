"""Extraction des événements : silver -> data/event/.

    silver    -> lecture d'un chapitre de la silver
    preparse  -> texte nettoyé (notes éditoriales et de couverture retirées,
                 texte normalisé) et décompte des suppressions
    entities  -> entités « sans futur » du chapitre (data/Entité/), table d'alias,
                 noms autorisés
    inputs    -> data/event/in/events_NNNN.md : le prompt utilisateur exact
    versions  -> versions du prompt et des entités, notées dans chaque sortie
    pipeline  -> orchestration, CLI

Voir la spec (issue #88) et l'ADR 0002 (taxonomie fermée des événements).
"""
