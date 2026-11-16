# ADR 0003 — Chapter embeddings : encodeur pré-entraîné gelé, exécuté en local

- **Statut :** accepté
- **Date :** 16 novembre 2026 (branche `dataset/vectorisation`)

Le Chapter embedding de chaque chapitre est produit par un encodeur de phrases pré-entraîné (sentence-transformers, `BAAI/bge-small-en-v1.5` par défaut, configuré dans le `.env`), utilisé **gelé** et exécuté en local, sur le seul Long Summary du chapitre. On écarte trois autres options :

- un **TF-IDF + SVD ajusté sur le corpus**, parce que son vocabulaire et ses poids viendraient des chapitres postérieurs à t, ce qui contredit l'ADR 0002 (le réajuster à chaque t serait coûteux et instable) ;
- un **encodeur fine-tuné avec le GRU**, parce qu'il faut un GPU et qu'environ 1 200 exemples ne suffisent pas pour l'entraîner sans surapprentissage ;
- l'**API d'embeddings du serveur de l'école**, parce qu'elle n'est joignable que depuis le réseau de l'école et n'est pas reproductible hors ligne.

Un encodeur gelé n'apprend rien du corpus : le vecteur du chapitre t ne dépend que du texte du chapitre t. Il peut donc être pré-calculé une fois pour toutes, en un dataset que le GRU consomme.

## Conséquences

- La vectorisation est une étape de pré-calcul indépendante. Elle écrit `data/gold/vector/chapter_embeddings.npz`, et le GRU ne fait que le lire.
- Changer de modèle oblige à recalculer tout le dataset, parce que des vecteurs de deux modèles ne sont pas comparables. Le nom du modèle est stocké dans le dataset pour le détecter.
- La fenêtre de l'encodeur (512 tokens) est plus courte qu'un Long Summary médian. On encode donc chaque Scene séparément, puis on en fait la moyenne pondérée par la longueur.
- `sentence-transformers` et `torch` sont dans un extra pip optionnel (`[vectorisation]`). L'ingestion, l'extraction d'entités et la CI n'en dépendent pas.
- Le texte n'est pas adapté à la tâche de prédiction. Si l'ablation montre que le texte seul n'apporte rien, la piste suivante est un encodeur plus grand ou fine-tuné, et cet ADR sera à revoir.
