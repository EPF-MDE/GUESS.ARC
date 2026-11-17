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
2. Une Scene plus longue que la fenêtre de l'encodeur (rare) est découpée en fenêtres de mots d'au plus 512 tokens (comptés par l'encodeur), qui se chevauchent d'environ un quart de fenêtre (au moins un mot). La dernière fenêtre finit au dernier mot de la Scene : la fin, souvent le cliffhanger, n'est jamais tronquée.
3. Chaque **Chunk** (une Scene entière, ou une fenêtre d'une Scene trop longue) est encodé en un vecteur.
4. Le Chapter embedding est la **moyenne des vecteurs, pondérée par la longueur** (en tokens) de chaque Chunk (une Scene de 300 mots pèse plus qu'une Scene de 20 mots).
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
skipped_chapters = [1196]                        # int, M chapitres sans Chapter embedding
skipped_reasons  = ["complete: false"]           # texte, M : raison du saut, même indice
+ métadonnées : modèle, dimension, méthode de pooling, date de génération
```

**La granularité par chapitre est garantie par l'alignement des lignes** : la ligne `i` de `embeddings` est le Chapter embedding du chapitre `chapters[i]`. Le vecteur du chapitre t s'obtient par `embeddings[chapters == t]`, jamais par la position seule.

Pour ne pas manipuler d'indices, le module fournit un chargeur :

```python
from guess_arc.vectorisation import load_chapter_embeddings

emb = load_chapter_embeddings()   # dict[int, np.ndarray] : {1: Chapter embedding, 2: Chapter embedding, ...}
emb[500].shape                    # (384,)
emb.skipped                       # {1196: "complete: false"} : chapitres sautés et raison
```

La Fusion joint ensuite les étapes **par numéro de chapitre** : `X[t] = concat(emb[t], events[t], ...)`.

Pourquoi un fichier unique plutôt qu'un fichier par chapitre : écriture atomique (pas de désynchronisation entre les vecteurs et leurs métadonnées), un seul `np.load` pour le GRU, et le fichier entier ne pèse que ~2 Mo (1 200 × 384 × 4 octets).

**Chapitres sautés.** Un chapitre marqué `complete: false` dans la silver (résumé trop court, repassé la semaine suivante par l'ingestion) ou dont le Long Summary est vide n'est pas vectorisé : il n'a pas de ligne dans `embeddings`, mais il est listé dans `skipped_chapters` avec sa raison (`complete: false`, `Long Summary vide`) dans `skipped_reasons`. Le chargeur l'expose dans `emb.skipped`, la commande affiche un `AVERTISSEMENT` avec le nombre et la liste des chapitres sautés, et le rapport qualité les liste aussi. La matrice ne contient aucune ligne de zéros : chaque Chapter embedding stocké a une norme de 1. La vectorisation ne comble aucun trou. Le traitement des trous dans la séquence (vecteur nul accompagné d'un masque, saut) est une décision de l'étape de Fusion, au moment de construire X(t). Un chapitre sauté n'a pas de `revision_id` stocké : il est vectorisé au premier run où il devient utilisable, et sort alors des chapitres sautés. Un dataset écrit avant l'ajout de `skipped_chapters` et `skipped_reasons` n'a pas ces tableaux : il est traité comme corrompu et entièrement recalculé au premier run.

## 7. Mise à jour incrémentale

Comme l'ingestion, la vectorisation tourne chaque semaine. Par défaut, `run` part du dataset existant :

- un chapitre absent du dataset, ou dont le `revision_id` en silver diffère de celui stocké, est (re)vectorisé ;
- un chapitre inchangé est conservé tel quel, avec le même Chapter embedding, sans appel à l'encodeur ;
- un chapitre devenu `complete: false`, ou disparu de la silver, est retiré du dataset ;
- si le modèle configuré (ou la méthode de pooling) diffère de celui du dataset, tout est recalculé : des vecteurs de deux modèles différents ne sont pas comparables ;
- si le dataset existant est corrompu, tout est recalculé. `dataset_problem` (dans `dataset.py`) décrit le problème au lieu de lever une exception : tableau manquant, tableau d'une forme ou d'un type inattendu (dimension qui n'est pas un entier scalaire, chapitres ou `revision_ids` qui ne sont pas des entiers 1-D, matrice qui n'est pas 2-D de flottants), lignes désalignées avec `chapters`, dimension différente des métadonnées, chapitre en double, NaN, norme différente de 1, chapitres sautés et raisons désalignés, chapitre sauté en double ou aussi vectorisé. Le chargeur transforme ce problème, comme une archive illisible, en `CorruptDatasetError` qui nomme `--rebuild`, et `run` en fait une raison de recalcul complet ;
- si l'encodeur rend des vecteurs d'une autre dimension sous le même nom de modèle, tout est recalculé plutôt que de mélanger deux dimensions. Les chapitres déjà encodés à cette exécution ne repassent pas par l'encodeur ;
- `run(..., rebuild=True)` et l'option `--rebuild` de la CLI forcent le recalcul complet. Il faut l'utiliser après tout changement du découpage (Scenes, Chunks) qui ne change ni le modèle ni le nom du pooling : un chapitre n'est « modifié » que si son `revision_id` change.

Quand rien n'est repris, la CLI affiche la raison (`recalcul complet : …`). Le résumé de la CLI et le rapport qualité (`vectorised` / `kept`) distinguent les chapitres vectorisés à cette exécution des chapitres conservés.

## 8. Contrôle qualité

Chaque exécution écrit `data/gold/vector/embeddings_quality.json` :

- nombre de chapitres vectorisés, liste des chapitres sautés et pourquoi ;
- dimension, présence de NaN, normes (toutes égales à 1) ;
- **cohérence sémantique** : similarité cosinus moyenne entre chapitres d'un même Arc (lu dans le front-matter) contre entre chapitres d'arcs différents. La première doit être nettement plus élevée : c'est une preuve simple que les vecteurs capturent le sens de l'histoire.

```json
{
  "model": "BAAI/bge-small-en-v1.5", "pooling": "chunk-mean-token-weighted-l2", "created_at": "…",
  "chapters": {"total": 1195, "vectorised": [1, 2, …], "kept": [], "skipped": {"1196": "complete: false"}},
  "dimension": 384, "nan_count": 0, "norm_min": 1.0, "norm_max": 1.0,
  "semantic_coherence": {"arcs": 33, "intra_arc_mean": …, "inter_arc_mean": …, "gap": …,
                         "intra_arcs": …, "arc_pairs": …}
}
```

Les moyennes sont **par Arc**, pour qu'un Arc long ne domine pas : `intra_arc_mean` est la moyenne, sur les `intra_arcs` Arcs d'au moins deux chapitres, de la similarité moyenne entre deux chapitres de l'Arc ; `inter_arc_mean` est la moyenne, sur les `arc_pairs` couples d'Arcs différents, de la similarité moyenne entre un chapitre de l'un et un chapitre de l'autre. Un Arc d'un seul chapitre n'a pas de moyenne intra-arc ; sans aucune moyenne, la valeur vaut `null`. `kept` liste les chapitres repris tels quels du dataset précédent (mise à jour incrémentale) ; `skipped` donne la raison de chaque saut (`complete: false`, `Long Summary vide`). Le dataset et le rapport sont écrits ensemble : chacun d'abord en entier dans un fichier temporaire du même dossier, puis ils remplacent les anciens l'un après l'autre. Si l'écriture d'un des fichiers temporaires échoue, les anciens fichiers restent intacts et aucun fichier temporaire ne reste. Seul un échec entre les deux remplacements peut laisser un nouveau dataset à côté d'un ancien rapport : le `created_at` du rapport est celui du dataset qu'il décrit, et s'il diffère de celui que rend `load_chapter_embeddings`, le rapport ne correspond pas au dataset.

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
