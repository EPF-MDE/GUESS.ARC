# Vectorisation des chapitres

Ce document explique le rôle de la vectorisation dans le pipeline GRU et la façon de l'implémenter. Vocabulaire : [CONTEXT.md](../CONTEXT.md). Décision d'architecture : [ADR 0003](adr/0003-chapter-embeddings-encodeur-gele.md).

## 1. Rôle dans le pipeline

Le modèle lit les chapitres 1 à t et prédit ce qui se passe au chapitre t+1 (voir `docs/Pipeline GRU.png`). Le GRU ne lit pas du texte : il lit une **séquence de vecteurs** x₁ → x₂ → … → xₜ, un par chapitre, et met à jour à chaque pas sa mémoire hₜ.

La vectorisation est l'étape 1 de ce schéma : elle transforme le texte de chaque chapitre en un **Chapter embedding**, un vecteur de taille fixe (384 nombres) qui résume le sens du chapitre. Ce vecteur est ensuite combiné, à l'étape de Fusion, avec les sorties des autres étapes (événements, Knowledge Graph, état narratif) pour former l'entrée X(t) du GRU :

```
X[t] = concat(chapter_embedding[t], events[t], kg[t], ...)
```

Les étapes 1 à 3 (vectorisation, entités, événements) sont indépendantes et tournent sur les mêmes chapitres. La vectorisation est aussi la première brique de l'ablation prévue : « texte seul », puis « + événements », « + Knowledge Graph », etc.

## 2. Qu'est-ce qu'un embedding ?

Un **embedding** est un vecteur de nombres produit par un réseau de neurones (un *encodeur*) à partir d'un texte, de telle sorte que deux textes de sens proche donnent des vecteurs proches. La proximité se mesure par la **similarité cosinus** : 1 si les vecteurs pointent dans la même direction, 0 s'ils n'ont rien en commun.

Exemple : « Luffy affronte Kaido sur le toit d'Onigashima » et « Le combat entre Luffy et Kaido continue » donnent des vecteurs très proches ; « Nami dessine une carte » en donne un éloigné. Le GRU n'a donc pas besoin de comprendre l'anglais : il reçoit des vecteurs dans lesquels le sens est déjà encodé.

## 3. Options comparées

| Méthode | Principe | Sens capturé | Fuite du futur (ADR 0002) | Coût |
|---|---|---|---|---|
| TF-IDF + SVD (LSA) | Fréquence des mots, réduite par algèbre linéaire | Lexical (mêmes mots) | **Oui** si ajusté sur tout le corpus : le vocabulaire et les poids viennent des chapitres futurs. Il faudrait le réajuster à chaque t. | Très faible |
| **Encodeur pré-entraîné gelé** (sentence-transformers) | Réseau entraîné sur des milliards de phrases, utilisé tel quel | Sémantique (paraphrases, contexte) | **Non** : il n'apprend rien du corpus, le vecteur du chapitre t ne dépend que du texte du chapitre t | Quelques minutes sur CPU pour tout le corpus |
| API d'embeddings (serveur LLM de l'école) | Idem, mais distant | Sémantique | Non | Dépend du réseau de l'école, pas reproductible hors ligne |
| Encodeur fine-tuné avec le GRU | Les poids de l'encodeur s'entraînent avec le GRU | Sémantique, adapté à la tâche | Maîtrisable, mais aucun dataset à produire | GPU nécessaire, ~1 200 exemples seulement |

**Choix retenu : encodeur pré-entraîné gelé, exécuté en local** (ADR 0003). Modèle par défaut : `BAAI/bge-small-en-v1.5`, 384 dimensions, fenêtre de 512 tokens. Le nom du modèle se règle dans le `.env` (`EMBEDDING_MODEL`), jamais dans le code. 384 dimensions restent raisonnables face à ~1 200 exemples d'entraînement : un vecteur plus grand favoriserait le surapprentissage du GRU.

## 4. Quel texte vectoriser ?

Uniquement le **Long Summary** du chapitre (`## Long Summary` de `data/silver/chapter_NNNN.md`).

- Le **Short Summary** manque dans ~4 % des chapitres et répète le Long Summary.
- Les **Chapter Notes** sont des remarques éditoriales du wiki (« first appearance of… », renvois à d'autres chapitres), parfois rétrospectives : risque de fuite du futur.
- La **liste des personnages** (front-matter) est déjà portée par l'étape Entités. La mettre aussi dans le vecteur brouillerait l'ablation « texte seul vs + entités ».

## 5. Le problème de la longueur

Un encodeur a une fenêtre limitée (512 tokens pour `bge-small`, environ 380 mots). Or, mesuré sur les 1 197 chapitres :

| | min | médiane | p95 | max |
|---|---|---|---|---|
| Mots par Long Summary | 97 | 598 | 1 083 | 2 094 |
| Scenes par chapitre | 1 | 5 | 8 | 16 |
| Mots par Scene | 4 | 114 | 271 | 818 |

Tronquer le chapitre à 512 tokens ferait perdre la fin, souvent le cliffhanger, c'est-à-dire l'information la plus utile pour prédire t+1. On découpe donc par **Scene** (un paragraphe du Long Summary), qui tient dans la fenêtre dans 95 % des cas :

1. Le Long Summary est découpé en Scenes (paragraphes non vides).
2. Une Scene plus longue que la fenêtre de l'encodeur (rare) est découpée en fenêtres de 512 tokens qui se chevauchent.
3. Chaque Scene (ou fenêtre) est encodée en un vecteur.
4. Le Chapter embedding est la **moyenne des vecteurs, pondérée par la longueur** de chaque morceau (une Scene de 300 mots pèse plus qu'une Scene de 20 mots).
5. Le résultat est **normalisé L2** (norme 1), pour que la similarité cosinus se réduise à un produit scalaire et que tous les chapitres aient la même échelle.

```
Long Summary ──► Scene 1 ──► encodeur ──► v₁ (384) ─┐
             ├─► Scene 2 ──► encodeur ──► v₂ (384) ─┼─► moyenne pondérée ─► L2 ─► Chapter embedding (384)
             └─► Scene k ──► encodeur ──► vₖ (384) ─┘
```

Les vecteurs par Scene ne sont pas conservés en v1.

## 6. Format de sortie

Un seul fichier : **`data/gold/vector/chapter_embeddings.npz`**.

Un `.npz` est une **archive zip de tableaux numpy nommés**. `np.load(...)` l'ouvre et renvoie une sorte de dictionnaire de tableaux. Celui-ci contient :

```
chapters     = [   1,    2,    3, ..., 1197]     # int, N chapitres
revision_ids = [ ...,  ...,  ..., ...,  ...]     # int, N : revision_id de la silver vectorisée
embeddings   = [[0.12, -0.40, ...],              # float32, N × 384
                [0.03,  0.91, ...],              # ligne i ↔ chapitre chapters[i]
                ...]
+ métadonnées : modèle, dimension, méthode de pooling, date de génération
```

**La granularité par chapitre est garantie par l'alignement des lignes** : la ligne `i` de `embeddings` est le Chapter embedding du chapitre `chapters[i]`. Le vecteur du chapitre t s'obtient par `embeddings[chapters == t]`, jamais par la position seule.

Pour ne pas manipuler d'indices, le module fournit un chargeur :

```python
from guess_arc.vectorisation import load_chapter_embeddings

emb = load_chapter_embeddings()   # dict[int, np.ndarray] : {1: vecteur, 2: vecteur, ...}
emb[500].shape                    # (384,)
```

La Fusion joint ensuite les étapes **par numéro de chapitre** : `X[t] = concat(emb[t], events[t], ...)`.

Pourquoi un fichier unique plutôt qu'un fichier par chapitre : écriture atomique (pas de désynchronisation entre les vecteurs et leurs métadonnées), un seul `np.load` pour le GRU, et le fichier entier ne pèse que ~2 Mo (1 200 × 384 × 4 octets).

**Chapitres absents.** Un chapitre marqué `complete: false` dans la silver (résumé trop court, repassé la semaine suivante par l'ingestion) n'est pas vectorisé : il n'a pas d'entrée dans le dataset. La vectorisation ne comble aucun trou. Le traitement des trous dans la séquence (vecteur nul, masque, saut) est une décision de l'étape de Fusion.

## 7. Mise à jour incrémentale

Comme l'ingestion, la vectorisation tourne chaque semaine :

- par défaut, seuls les chapitres absents du dataset, ou dont le `revision_id` en silver diffère de celui stocké, sont (re)vectorisés ;
- si le modèle configuré diffère de celui du dataset, tout est recalculé (des vecteurs de deux modèles différents ne sont pas comparables) ;
- `--rebuild` force le recalcul complet.

## 8. Contrôle qualité

Chaque exécution écrit `data/gold/vector/embeddings_quality.json` :

- nombre de chapitres vectorisés, liste des chapitres sautés et pourquoi ;
- dimension, présence de NaN, normes (toutes égales à 1) ;
- **cohérence sémantique** : similarité cosinus moyenne entre chapitres d'un même arc (arc lu dans le front-matter) contre entre chapitres d'arcs différents. La première doit être nettement plus élevée : c'est une preuve simple que les vecteurs capturent le sens de l'histoire.

## 9. Lien avec l'ADR 0002 (connaissance du lecteur)

Le Chapter embedding du chapitre t ne dépend **que du texte du chapitre t** et d'un encodeur entraîné hors du corpus, donc sans rien savoir de One Piece après t. Il ne fait fuiter aucune information future, ni dans les entrées du GRU, ni dans l'évaluation. Seule limite, déjà acceptée par l'ADR 0002 : le Long Summary vient de la révision actuelle du wiki et peut contenir des formulations rétrospectives.

## 10. Installation et utilisation

Les dépendances de la vectorisation (`sentence-transformers`, qui installe `torch` en version CPU, environ 200 Mo) sont dans un **extra optionnel**, pour que l'ingestion et les tests restent légers :

```bash
pip install -e .[vectorisation]
```

Dans le `.env` :

```
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
```

Au premier lancement, le modèle est téléchargé depuis Hugging Face (~130 Mo) puis mis en cache : les exécutions suivantes tournent hors ligne.

```bash
python -m guess_arc.vectorisation             # incrémental
python -m guess_arc.vectorisation --rebuild   # recalcul complet
```

Les tests n'ont besoin ni de cet extra ni du réseau : l'encodeur est derrière une interface `encode(texts) -> array`, et les tests utilisent un encodeur factice déterministe.
