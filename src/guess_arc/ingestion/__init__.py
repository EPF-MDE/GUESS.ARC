"""Ingestion bronze + silver depuis le wiki Fandom anglais.

    wiki_client  -> appels à l'API MediaWiki
    parser       -> wikitexte d'une page de chapitre -> Chapter
    silver       -> Chapter -> data/silver/chapter_NNNN.md
    validation   -> contrat de format des couches bronze et silver
    pipeline     -> orchestration, état incrémental, CLI

Le contenu Fandom est sous licence CC BY-SA. Usage académique avec attribution.
"""
