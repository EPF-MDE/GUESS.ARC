# GUESS.ARC — Contexte de domaine

Prédiction, par apprentissage automatique, des tags du chapitre n+1 de One
Piece à partir de l'historique des chapitres précédents. Ce fichier fixe le
vocabulaire du pipeline de données ; il ne décrit ni l'architecture ni
l'implémentation.

## Langage

**Bronze**:
Archive brute d'un chapitre, telle que récupérée depuis le wiki (wikitext +
métadonnées de révision), sans transformation. Un enregistrement JSONL par
chapitre.
_Avoid_: donnée brute, scrap

**Silver**:
Version nettoyée et structurée d'un chapitre : un fichier Markdown avec
front-matter (numéro, titre, arc, personnages avec faction et présence à
l'écran) et sections de texte libre (`Short Summary`, `Long Summary`,
`Chapter Notes`). C'est la forme de référence d'un chapitre pour toute
extraction ultérieure.
_Avoid_: donnée nettoyée, chapitre parsé

**Gold**:
Dossier contenant, pour chaque chapitre, un fichier JSON avec les tags de
taxonomie extraits pour ce chapitre. Distinct de la matrice binaire
chapitre × label évoquée initialement dans
`onepiece-faisabilite/faisabilite-etat-de-lart.md` : cette matrice, si elle
est construite, sera dérivée de gold, pas gold elle-même.
_Avoid_: donnée labellisée, matrice, dataset d'entraînement

**Taxonomie**:
L'ensemble des champs et valeurs autorisées utilisés pour tagger un
chapitre. Définie et maintenue par une personne dédiée, en dehors de la
couche d'appel API ; injectée dans le prompt système au moment de l'appel,
jamais codée en dur dans le client. Rafraîchie périodiquement (révisions
hebdomadaires envisagées).
_Avoid_: schéma, labels (seuls, sans préciser lesquels)

**Corpus**:
L'ensemble des 1193 chapitres ingérés (`data/bronze/`, `data/silver/`).
_Avoid_: dataset, jeu de données
