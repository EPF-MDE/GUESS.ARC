"""Extraction des événements : silver -> data/event/.

    silver    -> lecture d'un chapitre de la silver
    preparse  -> texte nettoyé (notes éditoriales et de couverture retirées,
                 texte normalisé) et décompte des suppressions
    entities  -> entités « sans futur » du chapitre (data/Entité/), table d'alias,
                 noms autorisés
    inputs    -> data/event/in/events_NNNN.md : le prompt utilisateur exact
    taxonomy  -> les 20 types d'événements que le modèle peut émettre (v1)
    prompt    -> prompt système versionné, exemple few-shot du ch. 97 (prompts/)
    schema    -> schéma JSON versionné de la réponse, noms autorisés injectés
    llm       -> client LLM : (prompt système, prompt utilisateur, schéma) -> texte
                 brut ; client factice pour les tests
    response  -> bloc de réflexion retiré, JSON parsé et validé contre le schéma
    extraction -> essais, pause entre deux appels, réponses brutes, run.jsonl
    checks    -> contrôles des événements llm : preuve, fuite du futur, doublons
    outputs   -> data/event/out/events_NNNN.json : fusion des origines wiki et llm
    versions  -> versions du prompt, du schéma, de la taxonomie et des
                 entités, notées dans chaque sortie
    pipeline  -> orchestration, CLI

Voir la spec (issue #88) et l'ADR 0002 (taxonomie fermée des événements).
"""
