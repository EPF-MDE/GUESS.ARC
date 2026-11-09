# Le GRU (Gated Recurrent Unit) appliqué à la prédiction narrative

> **Note de recherche technique** — Projet « Prédire les événements du prochain chapitre de *One Piece* »
> Périmètre : l'étape 7 du pipeline (GRU) et ses interfaces avec l'étape 6 (Fusion) et l'étape 8 (Classifieur de prédiction).
> Rédigée le 27 octobre 2026.

**Plan**

0. Contexte : où se place le GRU dans notre pipeline
1. Qu'est-ce qu'un GRU ?
2. Fonctionnement détaillé
3. Pourquoi des données diversifiées plutôt que du texte brut ?
4. Comment le GRU exploite les vecteurs combinés $x_1, x_2, \dots, x_t$
5. Ressources pour aller plus loin

---

## 0. Contexte : où se place le GRU dans notre pipeline

Le modèle lit les chapitres $1 \dots t$ et prédit les événements du chapitre $t+1$. Le GRU est la **mémoire** du système : il reçoit, chapitre après chapitre, un vecteur combiné $x_k$ produit par la fusion, et maintient un résumé $h_k$ de toute l'histoire lue jusque-là. Dans la version de base, le classifieur ne voit **que** $h_t$.

```text
                     Chapitres 1 … t  (résumés en anglais)
            ┌────────────────────┼─────────────────────────┐
            ▼                    ▼                         ▼
   (1) Vectorisation     (2) Extraction des entités   (3) Extraction des événements
            │                    │                         │
            │                    ▼                         │
            │      (4) Knowledge Graph KG(t)               │
            │          entités + relations des ch. 1…t     │
            │                    │                         │
            │                    ▼                         │
            │      (5) État narratif  ◄────────────────────┤
            │                    │                         │
            ▼                    ▼                         ▼
   (6) Fusion des sorties 1, 3, 4, 5  ─────────►  x_1, x_2, …, x_t
                                                       │
                                                       ▼
   (7) GRU :  h_k = GRU(x_k, h_{k-1})   ─────────►  h_1 → h_2 → … → h_t
                                                       │
                                                       ▼
   (8) Classifieur de prédiction  ──────────────►  Top-K événements prédits pour t+1
 ═════════════════ AUCUNE INFORMATION POSTÉRIEURE AU CHAPITRE t ═════════════════
   (9)  Extraction des événements du chapitre t+1 (même outil qu'en 3)  →  vérité terrain
   (10) Évaluation : F1, Précision@K
```

### Notations utilisées dans tout le document

| Symbole | Signification | Dimension |
|---|---|---|
| $t$ | indice de chapitre (temps narratif) | — |
| $x_t$ | vecteur combiné du chapitre $t$ (sortie de l'étape 6) | $d_x$ |
| $h_t$ | état caché = mémoire de l'histoire après lecture du chapitre $t$ | $d_h$ |
| $r_t$ | porte de réinitialisation (*reset gate*) | $d_h$ |
| $z_t$ | porte de mise à jour (*update gate*) | $d_h$ |
| $\tilde h_t$ | état candidat (nouvelle information proposée) | $d_h$ |
| $\sigma$ | fonction sigmoïde, à valeurs dans $]0, 1[$ | — |
| $\odot$ | produit élément par élément (Hadamard) | — |
| $C$ | nombre de types d'événements à prédire | — |

---

## 1. Qu'est-ce qu'un GRU ?

### 1.1 Définition

Un **GRU** (*Gated Recurrent Unit*, « unité récurrente à portes ») est une cellule de réseau de neurones récurrent (RNN). Elle lit une séquence élément par élément et met à jour un **unique vecteur d'état** $h_t$ qui sert à la fois de mémoire et de sortie.

Sa particularité tient à deux **portes** apprises, des vecteurs de valeurs entre 0 et 1 calculés à chaque pas :

- la **porte de mise à jour** $z_t$ décide, dimension par dimension, quelle part de l'ancienne mémoire conserver et quelle part remplacer ;
- la **porte de réinitialisation** $r_t$ décide quelle part de l'ancienne mémoire consulter pour fabriquer la nouvelle information.

Pour notre projet : à chaque chapitre, le GRU décide ce qu'il retient (alliances, conflits ouverts, mystères non résolus), ce qu'il oublie (détails d'un arc terminé) et ce qu'il écrit (ce que le chapitre apporte de neuf).

### 1.2 Origine

- **1990** — Elman popularise le RNN simple : un état caché recalculé à chaque pas.
- **1994** — Bengio, Simard et Frasconi démontrent qu'apprendre des dépendances longues par descente de gradient dans un RNN est intrinsèquement difficile (disparition / explosion du gradient).
- **1997** — Hochreiter et Schmidhuber proposent le **LSTM**, avec une cellule mémoire séparée protégée par des portes. La porte d'oubli du LSTM « moderne » est ajoutée ensuite (Gers et al., 2000).
- **2014** — **Cho et al.** introduisent, dans leur article sur l'encodeur-décodeur RNN pour la traduction automatique (EMNLP 2014), une nouvelle unité cachée « qui se souvient et oublie de façon adaptative ». C'est le GRU.
- **Fin 2014** — **Chung, Gulcehre, Cho et Bengio** la baptisent explicitement *gated recurrent unit* et la comparent au LSTM sur la modélisation de musique polyphonique et de signaux de parole : les deux unités à portes battent nettement le RNN simple, et le GRU se révèle **comparable** au LSTM.
- **2015** — Jozefowicz, Zaremba et Sutskever évaluent plus de dix mille architectures récurrentes. Aucune ne domine partout ; ils montrent aussi qu'initialiser à 1 le biais de la porte d'oubli du LSTM comble l'écart avec le GRU.

### 1.3 Le problème de départ : la disparition du gradient dans un RNN simple

Un RNN simple calcule :

$$
h_t = \tanh\!\left(W x_t + U h_{t-1} + b\right)
$$

Pour apprendre qu'un événement du chapitre $k$ influence la prédiction au chapitre $t$, l'erreur doit être rétropropagée à travers le temps (*backpropagation through time*, BPTT). Le gradient fait alors intervenir un **produit de jacobiennes** :

$$
\frac{\partial h_t}{\partial h_k} \;=\; \prod_{j=k+1}^{t} \operatorname{diag}\!\big(1 - h_j^{2}\big)\, U
$$

La même matrice $U$ est multipliée $t-k$ fois. Si le facteur de contraction effectif vaut $\gamma < 1$, l'influence décroît comme $\gamma^{\,t-k}$ : c'est la **disparition du gradient**. S'il vaut plus que 1, le gradient **explose**.

Ordres de grandeur avec $\gamma = 0{,}9$ :

| Distance (chapitres) | $0{,}9^{\,t-k}$ | Lecture pour *One Piece* |
|---|---|---|
| 10 | $\approx 0{,}35$ | un indice donné au début d'un combat reste exploitable |
| 50 | $\approx 5 \times 10^{-3}$ | un arc entier : le signal est déjà quasi noyé |
| 100 | $\approx 3 \times 10^{-5}$ | un événement de l'arc précédent : inapprenable en pratique |
| 500 | $\approx 10^{-23}$ | un indice semé des centaines de chapitres plus tôt : invisible |

Or une œuvre de plus de 1 100 chapitres est précisément faite de dépendances longues : des mystères posés très tôt, des personnages qui reviennent après des centaines de chapitres d'absence, des promesses tenues des arcs plus tard.

### 1.4 Avantages du GRU face au RNN simple

Le GRU remplace la réécriture complète $h_t = f(h_{t-1}, x_t)$ par une **interpolation** contrôlée par la porte $z_t$ :

$$
h_t = z_t \odot h_{t-1} + (1 - z_t) \odot \tilde h_t
$$

Quand $z_t \approx 1$ sur une dimension, cette dimension est recopiée quasiment telle quelle. Le gradient emprunte alors un **chemin additif presque identitaire**, comparable à une connexion résiduelle à travers le temps. Le réseau peut **apprendre** à garder une information sur des dizaines ou des centaines de chapitres (démonstration en section 2.6).

### 1.5 GRU contre LSTM

| | RNN simple | LSTM | GRU |
|---|---|---|---|
| Année | 1990 | 1997 (porte d'oubli : 2000) | 2014 |
| Portes | 0 | 3 : oubli, entrée, sortie | 2 : mise à jour, réinitialisation |
| États propagés | $h_t$ | $h_t$ et cellule $c_t$ | $h_t$ seulement |
| Blocs de poids | 1 | 4 | 3 |
| Paramètres par couche (PyTorch) | $d_h(d_x + d_h + 2)$ | $4\,d_h(d_x + d_h + 2)$ | $3\,d_h(d_x + d_h + 2)$ |
| Exemple $d_x = 512$, $d_h = 256$ | 197 120 | 788 480 | **591 360** |
| Chemin du gradient | produit de matrices | additif via $c_t$ | additif via $z_t$ |
| Explosion du gradient | oui | possible | possible |

Les arguments en faveur du GRU pour notre projet :

- **Légèreté** : 3 blocs de poids au lieu de 4, soit environ 25 % de paramètres et de calcul en moins par pas de temps.
- **Petit volume de données** : nous n'avons qu'**une seule histoire**, soit environ un millier d'exemples. Moins de paramètres signifie moins de capacité à sur-apprendre. C'est une heuristique, pas une loi : les comparaisons publiées ne désignent pas de vainqueur universel entre GRU et LSTM.
- **Un seul état** : un seul vecteur $h_t$ à mettre en cache, à sonder et à visualiser (voir section 4.8).
- **Moins d'hyperparamètres** sensibles. Le LSTM demande en pratique d'initialiser le biais d'oubli à 1 pour bien fonctionner.

Le LSTM conserve un atout : sa porte de sortie lui permet de garder une information en mémoire **sans l'exposer** au reste du réseau, alors que le GRU expose tout son état. Recommandation : **partir du GRU**, puis faire une ablation GRU / LSTM une fois le pipeline stable. Avec `nn.GRU` → `nn.LSTM`, le changement tient en une ligne.

### 1.6 Ce que le GRU ne résout pas

- **L'explosion du gradient** reste possible : il faut **toujours** écrêter la norme du gradient (*gradient clipping*, Pascanu et al., 2013).
- **La disparition du gradient** est **atténuée**, pas supprimée : elle est simplement rendue apprenable.
- **Le goulot d'étranglement** demeure : toute l'histoire doit tenir dans un vecteur de taille fixe $d_h$, par exemple 256 nombres. D'où l'intérêt de fournir au GRU des entrées déjà structurées (section 3).
- **Le calcul est séquentiel** dans le temps. Avec un millier de chapitres, ce n'est pas un problème.

---

## 2. Fonctionnement détaillé

### 2.1 Schéma d'une cellule

```text
                  h_{t-1} ───────────────────────────┬──────────────(× z_t)──────┐
                     │                               │                           │
                     ▼                               ▼                           ▼
   x_t ──►  ┌─────────────────┐            ┌──────────────────┐                (+) ──► h_t
            │ r_t = σ(·)      │──(r_t ⊙)──►│ h̃_t = tanh(·)    │──(× (1 − z_t))──┘
            │ z_t = σ(·)      │            │ candidat         │
            └─────────────────┘            └──────────────────┘
   r_t : quelle part du passé RELIRE pour fabriquer le candidat
   z_t : quelle part du passé GARDER telle quelle (le reste est remplacé par h̃_t)
```

### 2.2 Les quatre équations

Convention de Cho et al. (2014), reprise par PyTorch, Keras et le manuel D2L :

$$
\begin{aligned}
r_t &= \sigma\!\left(W_r x_t + U_r h_{t-1} + b_r\right) && \text{(porte de réinitialisation)}\\
z_t &= \sigma\!\left(W_z x_t + U_z h_{t-1} + b_z\right) && \text{(porte de mise à jour)}\\
\tilde h_t &= \tanh\!\left(W_h x_t + U_h\,(r_t \odot h_{t-1}) + b_h\right) && \text{(état candidat)}\\
h_t &= z_t \odot h_{t-1} + (1 - z_t) \odot \tilde h_t && \text{(nouvelle mémoire)}
\end{aligned}
$$

> ⚠️ **Piège de convention.** Dans Chung et al. (2014) et dans le cours d'Andrew Ng, les rôles sont inversés : $h_t = (1 - z_t)\odot h_{t-1} + z_t \odot \tilde h_t$, donc $z_t \approx 1$ signifie « écrire ». **Dans ce document et dans PyTorch, $z_t \approx 1$ signifie « garder la mémoire ».** À vérifier à chaque lecture d'article ou de tutoriel.

> ℹ️ **Variante d'implémentation.** PyTorch applique $r_t$ **après** le produit matriciel : $\tilde h_t = \tanh\!\left(W_h x_t + b_{ih} + r_t \odot (U_h h_{t-1} + b_{hh})\right)$. La documentation précise que cet écart avec l'article originel est voulu, pour l'efficacité. Keras / TensorFlow 2 font de même par défaut (`reset_after=True`). Les deux variantes se comportent de façon très proche ; il faut seulement le savoir pour comparer des poids ou réimplémenter la cellule (section 2.8).

### 2.3 La porte de réinitialisation $r_t$ (*reset gate*)

**Rôle** : contrôler à quel point l'ancienne mémoire $h_{t-1}$ participe à la construction du candidat $\tilde h_t$.

- $r_t \approx 0$ sur une dimension : le candidat est construit **presque uniquement à partir du chapitre courant** $x_t$. C'est une « page blanche » locale.
- $r_t \approx 1$ : le candidat combine le chapitre courant **et** le contexte accumulé.

**Lecture narrative.** Au début d'un nouvel arc, après une ellipse temporelle ou lors d'un flashback, le contexte local de l'arc précédent n'aide pas à interpréter le chapitre courant. Une porte $r_t$ basse sur les dimensions « contexte local » évite de contaminer la nouvelle information. En plein combat, au contraire, le sens du chapitre courant dépend fortement de ce qui précède : $r_t$ reste haute.

> $r_t$ **n'efface pas** la mémoire. Elle agit seulement sur le **calcul du candidat**. L'effacement effectif passe par $z_t$.

### 2.4 La porte de mise à jour $z_t$ (*update gate*)

**Rôle** : interpoler, dimension par dimension, entre « garder » ($z_t \approx 1$) et « remplacer par le candidat » ($z_t \approx 0$).

C'est la pièce maîtresse du GRU. Elle fusionne en une seule porte ce que le LSTM répartit entre porte d'oubli et porte d'entrée : ce qui est gardé et ce qui est écrit sont **complémentaires** par construction ($z_t$ et $1 - z_t$).

**Interprétation en échelle de temps.** Si $z$ reste à peu près constant sur une dimension, la contribution d'un chapitre lu $k$ chapitres plus tôt est pondérée par $z^k$. On en déduit une **demi-vie mémoire** $k_{1/2} = \ln(0{,}5) / \ln(z)$ et une constante de temps $\tau = 1/(1 - z)$ :

| $z$ moyen | Demi-vie (chapitres) | Constante de temps $\tau$ | Ce que la dimension peut suivre |
|---|---|---|---|
| 0,5 | 1 | 2 | ce qui vient de se passer |
| 0,9 | 6,6 | 10 | une scène, un combat court |
| 0,95 | 13,5 | 20 | un combat long, une sous-intrigue |
| 0,99 | 69 | 100 | un arc entier |
| 0,999 | 693 | 1 000 | composition de l'équipage, mystères de fond |

Chaque dimension de $h_t$ possède **sa propre** porte. Le GRU peut donc apprendre une **mémoire multi-échelle** : certaines dimensions « rapides » suivent l'action immédiate, d'autres « lentes » conservent les faits structurants de la série. Comme $z_t$ dépend aussi de $x_t$, ces échelles **s'adaptent au contenu** : une dimension lente peut s'ouvrir brusquement quand un chapitre change la donne (révélation, trahison, mort d'un personnage). Tallec et Ollivier (2018) formalisent cette intuition : des portes apprenables rendent le réseau quasi invariant aux déformations du temps, ce qui revient à apprendre des constantes de temps locales.

### 2.5 La mise à jour de la mémoire $h_t$

$$
h_t \;=\; \underbrace{z_t \odot h_{t-1}}_{\text{ce qu'on garde}} \;+\; \underbrace{(1 - z_t) \odot \tilde h_t}_{\text{ce qu'on écrit}}
$$

En réécrivant $h_t - h_{t-1} = (1 - z_t) \odot (\tilde h_t - h_{t-1})$, on voit que le GRU est un **intégrateur à fuite** (*leaky integrator*). À chaque chapitre, la mémoire fait un pas, de taille $1 - z_t$, vers ce que propose le chapitre. Comme $h_t$ est une moyenne pondérée de $h_{t-1}$ et de $\tilde h_t \in [-1, 1]$, l'état reste **borné**, ce qui stabilise la dynamique sur un millier de pas.

### 2.6 Pourquoi le gradient survit : l'analyse

La jacobienne d'un pas de GRU (convention de Cho) se décompose en trois termes :

$$
\frac{\partial h_t}{\partial h_{t-1}}
= \underbrace{\operatorname{diag}(z_t)}_{\text{chemin direct}}
+ \operatorname{diag}(1 - z_t)\,\frac{\partial \tilde h_t}{\partial h_{t-1}}
+ \operatorname{diag}(h_{t-1} - \tilde h_t)\,\operatorname{diag}\!\big(z_t \odot (1 - z_t)\big)\,U_z
$$

Quand $z_t \to 1$ sur une dimension, les deux derniers termes s'annulent (ils contiennent $1 - z_t$) et il ne reste que $\operatorname{diag}(z_t) \approx I$. Sur une distance de $t-k$ chapitres, le gradient est alors multiplié par environ $\prod_j z_j$ plutôt que par une puissance de matrice.

| Distance | RNN simple ($\gamma = 0{,}9$) | GRU, dimension « lente » ($z = 0{,}99$) | GRU, dimension « très lente » ($z = 0{,}999$) |
|---|---|---|---|
| 100 chapitres | $3 \times 10^{-5}$ | 0,37 | 0,90 |
| 500 chapitres | $10^{-23}$ | $6{,}6 \times 10^{-3}$ | 0,61 |

**Conséquence pratique : l'initialisation.** Au départ de l'entraînement, $z_t \approx \sigma(0) = 0{,}5$, soit une demi-vie d'un seul chapitre. Le réseau doit alors « découvrir » qu'il faut mémoriser longtemps, à travers un gradient déjà très atténué. L'**initialisation chrono** (Tallec et Ollivier, 2018) tire les biais de porte selon $\log\big(\mathcal{U}[1, T_{\max} - 1]\big)$. Transposée à la porte $z$ de PyTorch, elle donne $z \approx 1 - 1/(1+u)$ : des constantes de temps initiales réparties entre 2 et $T_{\max}$ chapitres. Les dimensions lentes existent donc dès le départ. Implémentation : fonction `chrono_init_` en section 4.6.

### 2.7 La séquentialité temporelle des chapitres

**1. Lecture causale stricte.** Le GRU lit $x_1, x_2, \dots, x_t$ **dans l'ordre de publication**. Par construction, $h_t$ ne dépend que des chapitres $\le t$, ce qui matérialise la règle « aucune information future après le chapitre $t$ » du schéma.

- **Interdit : `bidirectional=True`** au niveau des chapitres. Un GRU bidirectionnel lirait aussi les chapitres futurs.
- **Autorisé** : un encodeur bidirectionnel **à l'intérieur** du texte d'un chapitre, à l'étape 1, puisque ce texte appartient au chapitre $t$.

**2. Un seul passage, toutes les prédictions (*many-to-many*).** Une passe sur la séquence produit $h_1, \dots, h_t$. Chaque $h_k$ prédit les événements du chapitre $k+1$. On obtient ainsi une perte sur **toutes** les positions à la fois, sans *teacher forcing*, puisque les entrées sont des chapitres réellement observés.

**3. État initial.** $h_0 = 0$, ou un vecteur appris, au chapitre 1. On ne réinitialise **jamais** l'état entre arcs : c'est au GRU d'apprendre quoi oublier.

**4. Entraîner sur une séquence de plus de 1 000 pas.** Deux options :

- **(A) BPTT complète.** Une passe sur tous les chapitres d'entraînement, puis un seul pas d'optimisation. C'est exact et peu coûteux (1 000 pas × 256 dimensions), mais ne donne qu'une mise à jour par passe et peu de stochasticité.
- **(B) Fenêtres aléatoires avec état stocké (recommandé).** À chaque époque, on calcule sans gradient tous les états $h_k$ sur la période d'entraînement. On tire ensuite des fenêtres de $W$ chapitres consécutifs, par exemple $W = 64$, initialisées avec l'état stocké juste avant la fenêtre. On obtient des mini-lots, des positions mélangées, et un état initial réaliste pour chaque fenêtre. La limite : le gradient ne remonte pas au-delà de $W$ chapitres, mais la **mémoire** portée par l'état stocké, elle, n'est pas tronquée. L'initialisation chrono compense en partie (code en section 4.6).

**5. Découpage temporel.** Entraînement sur les chapitres $1..N$, validation sur $N+1..M$, test sur $M+1..T$. On ne mélange jamais. Pour prédire un chapitre de test, le GRU lit **tous** les chapitres précédents, y compris ceux d'entraînement et de validation. C'est légitime : ce sont des chapitres passés.

**6. Échelle hiérarchique (piste d'extension).** Si les dépendances très longues restent mal capturées, on peut empiler un second GRU, lent, qui ne se met à jour qu'aux frontières d'arc, à la manière des RNN hiérarchiques d'El Hihi et Bengio (1995). On peut aussi ajouter une attention sur les états passés (section 4.5).

### 2.8 Implémentation de référence : une cellule écrite à la main

Cette cellule reproduit exactement `nn.GRU`, avec la variante *reset-after* de PyTorch, et **renvoie les portes**. Elle permet de vérifier sa compréhension des équations, puis de **diagnostiquer** un modèle entraîné en traçant $z_t$ et $r_t$ chapitre par chapitre.

```python
import torch
import torch.nn as nn


class GRUCellPyTorchStyle(nn.Module):
    """Cellule GRU écrite « à la main », équivalente à nn.GRU de PyTorch
    (porte de réinitialisation appliquée APRÈS le produit W_hn · h_{t-1}).
    Elle renvoie aussi r_t et z_t : pratique pour inspecter les portes chapitre par chapitre."""

    def __init__(self, d_x: int, d_h: int):
        super().__init__()
        self.d_h = d_h
        self.W_i = nn.Linear(d_x, 3 * d_h)  # [W_ir | W_iz | W_in] + [b_ir | b_iz | b_in]
        self.W_h = nn.Linear(d_h, 3 * d_h)  # [W_hr | W_hz | W_hn] + [b_hr | b_hz | b_hn]

    def forward(self, x_t, h_prev):
        gi_r, gi_z, gi_n = self.W_i(x_t).chunk(3, dim=-1)
        gh_r, gh_z, gh_n = self.W_h(h_prev).chunk(3, dim=-1)
        r_t = torch.sigmoid(gi_r + gh_r)           # porte de réinitialisation
        z_t = torch.sigmoid(gi_z + gh_z)           # porte de mise à jour
        n_t = torch.tanh(gi_n + r_t * gh_n)        # état candidat (h̃_t)
        h_t = z_t * h_prev + (1.0 - z_t) * n_t     # z_t ≈ 1  ⇒  on garde la mémoire
        return h_t, r_t, z_t

    @classmethod
    def from_nn_gru(cls, gru: nn.GRU, layer: int = 0):
        """Copie les poids d'une couche de nn.GRU (pour diagnostiquer un modèle entraîné)."""
        cell = cls(gru.input_size if layer == 0 else gru.hidden_size, gru.hidden_size)
        with torch.no_grad():
            cell.W_i.weight.copy_(getattr(gru, f"weight_ih_l{layer}"))
            cell.W_i.bias.copy_(getattr(gru, f"bias_ih_l{layer}"))
            cell.W_h.weight.copy_(getattr(gru, f"weight_hh_l{layer}"))
            cell.W_h.bias.copy_(getattr(gru, f"bias_hh_l{layer}"))
        return cell


if __name__ == "__main__":
    torch.manual_seed(0)
    T, d_x, d_h = 50, 32, 16                       # 50 chapitres, vecteurs x_t de dimension 32
    gru = nn.GRU(d_x, d_h, batch_first=True)
    x = torch.randn(1, T, d_x)
    H_ref, _ = gru(x)                              # h_1 … h_T calculés par PyTorch

    cell = GRUCellPyTorchStyle.from_nn_gru(gru)
    h = torch.zeros(1, d_h)
    H_mano, Z = [], []
    for t in range(T):                             # on « lit » les chapitres dans l'ordre
        h, r, z = cell(x[:, t], h)
        H_mano.append(h)
        Z.append(z)
    H_mano = torch.stack(H_mano, dim=1)

    print("écart max avec nn.GRU :", (H_mano - H_ref).abs().max().item())   # ~1e-7
    print("z moyen par chapitre (5 premiers) :", torch.stack(Z, 1).mean(-1)[0, :5])
```

Pour la variante originelle de Cho et al. (*reset-before*), il suffit de remplacer la ligne du candidat par `n_t = torch.tanh(gi_n + self.W_h_n(r_t * h_prev))`, avec une couche linéaire dédiée `W_h_n`.

---

## 3. Pourquoi des données diversifiées plutôt que du texte brut ?

### 3.1 Le vrai goulot : une seule histoire, environ un millier d'exemples

Trois contraintes rendent le texte brut seul insuffisant :

1. **Rareté des exemples.** Une seule série, soit un exemple par chapitre, fortement autocorrélés entre eux. À titre de comparaison, le seul GRU de l'exemple de la section 1.5 compte environ 590 000 paramètres, pour quelques centaines de chapitres d'entraînement. Le modèle ne peut pas apprendre la *compréhension* de la langue et du récit à partir de nos seules données. Il doit recevoir des **représentations déjà digérées**.
2. **Goulot d'étranglement de $h_t$.** Toute l'histoire doit tenir dans $d_h$ nombres. Plus l'entrée est structurée, moins le GRU dépense de capacité à reconstruire des faits (« qui est allié de qui ? ») et plus il en garde pour modéliser la **dynamique** (« que se passe-t-il ensuite ? »).
3. **Longueur.** Un GRU sur les tokens bruts de toute la série devrait traverser des millions de pas de temps. Au niveau chapitre, il en traverse environ un millier.

Chaque source du pipeline est donc un **biais inductif** : elle injecte une connaissance que le modèle n'aurait pas les données pour découvrir seul.

### 3.2 Ce que chaque source apporte

#### 3.2.1 Vecteurs textuels (étape 1) : le « quoi » global et l'implicite

- **Ce qu'ils captent** : le contenu sémantique global, le ton, l'atmosphère, les sous-entendus et indices (*foreshadowing*), tout ce que les extracteurs ne savent pas mettre dans une case.
- **Problème résolu** : la **couverture**. Les étapes 2 à 5 ne voient que ce que leur schéma prévoit ; le vecteur texte est le filet de sécurité.
- **Limites** : la représentation est dense et intriquée, sans « qui a fait quoi » explicite. Les chapitres d'un même arc se ressemblent beaucoup (même décor, mêmes personnages), si bien que le vecteur encode souvent **l'arc** plus que **l'événement**.
- **Conseil** : les résumés peuvent dépasser la fenêtre de l'encodeur. Découper en passages, encoder, puis moyenner (*mean pooling*).

#### 3.2.2 Entités (étape 2) : le « qui » et l'identité stable

- **Ce qu'elles captent** : quels personnages, lieux, groupes et objets sont présents dans le chapitre.
- **Problème résolu** : la **coréférence et la stabilité des identités**. Un même personnage apparaît sous son nom, son surnom, son titre ou son épithète. Normaliser vers un identifiant canonique (Luffy = « Straw Hat » = « Monkey D. Luffy ») donne au GRU un **point d'ancrage** stable pour les dépendances longues : un personnage absent pendant 200 chapitres puis de retour est reconnu comme le même.
- **Problème résolu (bis)** : **qui est en scène** contraint fortement ce qui peut arriver au chapitre suivant.
- **Place dans le pipeline** : les entités n'entrent pas directement dans la fusion (étape 6) ; elles forment les nœuds du KG (étape 4). Leur qualité conditionne donc tout l'apport du KG. On peut ajouter au bloc KG un vecteur de présence (multi-hot) sur les $N$ entités les plus fréquentes, pour signaler explicitement qui est en scène.

#### 3.2.3 Événements (étape 3) : le « que s'est-il passé » dans l'espace de la cible

- **Ce qu'ils captent** : des faits typés avec participants, par exemple `combat(Luffy, ennemi X)`.
- **Problème résolu** : **l'alignement avec la cible**. Les événements d'entrée vivent dans le même espace que ce qu'on prédit (étape 9, même outil). Le GRU peut apprendre directement des **transitions** entre événements (combat → révélation → départ), ce qui est l'idée des *scripts narratifs* (Chambers et Jurafsky, 2008 ; Pichotta et Mooney, 2016). C'est aussi un **débruitage** : on passe de milliers de mots à une poignée de faits.
- **Point d'attention** : comme le même extracteur produit entrées et cibles, ses erreurs systématiques se retrouvent **des deux côtés**. Le score mesure alors l'accord avec l'extracteur, pas avec la vérité. Prévoir un **petit jeu « or » annoté à la main** (une cinquantaine de chapitres de test) pour mesurer la qualité de l'extracteur et le score réel du modèle.

#### 3.2.4 Relations du Knowledge Graph (étape 4) : le « comment c'est relié » et la persistance

- **Ce qu'il capte** : les relations entre entités (allié, membre de, ennemi de, capitaine de…) accumulées sur les chapitres $1..t$.
- **Problème résolu n° 1 : la persistance des faits.** Une alliance conclue au chapitre 50 reste vraie au chapitre 400 sans être répétée dans le texte. Sans KG, le GRU devrait garder ce fait dans $h_t$ pendant 350 pas. Avec le KG, le fait est **réinjecté** à chaque chapitre. Cela **soulage le goulot de mémoire**.
- **Problème résolu n° 2 : le raisonnement relationnel à plusieurs sauts** (l'ennemi d'un allié, le capitaine d'un équipage rival), qu'un vecteur de texte capte mal.
- **Encodage** : un GNN relationnel sur le graphe, puis une agrégation (*pooling*) ; ou des embeddings des entités actives. Fournir **l'instantané** $KG(t)$ **et la différence** $\Delta KG(t)$, c'est-à-dire les arêtes ajoutées ou retirées au chapitre $t$ : le changement est souvent plus prédictif que l'état.
- **Littérature proche** : RE-Net (Jin et al., 2020), RE-GCN (Li et al., 2021) et EvolveGCN (Pareja et al., 2020) couplent un encodeur de graphe et une récurrence pour prédire l'avenir d'un graphe temporel. C'est très proche de notre problème.

#### 3.2.5 État narratif (étape 5) : le « où en est-on »

- **Ce qu'il capte** : le statut des fils narratifs, par exemple « Luffy : actif », « conflit X : en cours », « mystère Y : ouvert ».
- **Problème résolu** : la **phase du récit**. Un conflit ouvert tend à se résoudre ; un combat annoncé tend à avoir lieu (le principe du fusil de Tchekhov). Cette « dette narrative » est probablement le prédicteur à court terme le plus fort. Elle est explicite ici au lieu d'être déduite.
- **Encodage** : des compteurs et indicateurs (conflits ouverts, durée depuis l'ouverture, personnages principaux actifs, blessés ou absents) et un embedding de l'arc courant.

### 3.3 Synthèse

| Source | Question à laquelle elle répond | Problème narratif résolu | Risque principal |
|---|---|---|---|
| Texte (1) | Que raconte ce chapitre, globalement ? | couverture, implicite, ton | encode l'arc plus que l'événement ; fuite via l'encodeur pré-entraîné |
| Entités (2) | Qui est en scène ? | coréférence, retours après longue absence | alias mal normalisés |
| Événements (3) | Que s'est-il passé ? | alignement avec la cible, transitions | erreurs corrélées entrée / cible |
| KG (4) | Comment les acteurs sont-ils liés ? | persistance des faits, multi-sauts | relations « du futur » injectées par erreur |
| État (5) | Où en sont les intrigues ? | dette narrative, phase de l'arc | règles de mise à jour fragiles |

Les sources sont **complémentaires** (chacune couvre un angle mort des autres) et partiellement **redondantes** (un combat apparaît dans le texte, les événements et l'état). Cette redondance est utile : elle rend le modèle robuste quand un extracteur se trompe.

### 3.4 Vérifier la complémentarité

Le plan d'expériences du schéma (texte seul → + événements → + KG → + GRU → modèle complet) est une ablation **cumulative**. Trois compléments le rendent concluant :

1. **Ablation « tout sauf une source »** : retirer une source à la fois du modèle complet. Une source peut sembler utile en ajout mais être redondante une fois les autres présentes.
2. **Isoler l'effet mémoire** : comparer le GRU à un MLP sur $x_t$ seul (aucune mémoire) **et** à un MLP sur la moyenne des $k$ derniers $x$ (mémoire à fenêtre fixe). Si le GRU ne bat pas la fenêtre fixe, la récurrence n'apporte rien de plus qu'un contexte court.
3. **Références triviales** à battre absolument : « fréquence globale des événements » et « persistance » (prédire pour $t+1$ les événements du chapitre $t$). En multi-label, elles sont souvent étonnamment fortes.

Enfin, une seule coupure train / test est bruitée, car les arcs diffèrent beaucoup. Mieux vaut évaluer sur **plusieurs origines glissantes**, par exemple entraîner jusqu'au chapitre 600 et tester sur 601–700, puis entraîner jusqu'à 700 et tester sur 701–800, etc. On rapporte alors une moyenne et un écart-type.

---

## 4. Comment le GRU exploite les vecteurs combinés $x_1, x_2, \dots, x_t$

### 4.1 Construction de $x_t$ (étape 6)

Chaque source est projetée dans un espace de même taille, puis **normalisée** avant concaténation :

$$
e^{(m)}_t = \mathrm{GELU}\!\Big(\mathrm{LayerNorm}\big(P_m\, s^{(m)}_t\big)\Big),
\qquad
x_t = \big[\, e^{\text{texte}}_t \;;\; e^{\text{evt}}_t \;;\; e^{\text{kg}}_t \;;\; e^{\text{état}}_t \,\big]
$$

Sans cette normalisation, un vecteur texte dense de 768 dimensions écraserait un vecteur d'événements creux (multi-hot). Il dominerait les pré-activations des portes simplement par sa norme, pas par son intérêt.

### 4.2 Pondération : la décomposition par blocs

Comme $x_t$ est une concaténation, chaque produit matriciel du GRU se décompose **par source** :

$$
W_z\, x_t \;=\; W_z^{\text{texte}}\, e^{\text{texte}}_t \;+\; W_z^{\text{evt}}\, e^{\text{evt}}_t \;+\; W_z^{\text{kg}}\, e^{\text{kg}}_t \;+\; W_z^{\text{état}}\, e^{\text{état}}_t
$$

Il en va de même pour $W_r$ et $W_h$. Concrètement :

- **Douze matrices de routage apprises** (3 usages × 4 sources). Une même source peut peser fortement dans la **décision d'écrire** ($W_z$) et peu dans le **contenu écrit** ($W_h$), ou l'inverse. Par exemple, un changement dans le KG peut déclencher l'écriture, tandis que le contenu écrit vient surtout du texte et des événements.
- **Une pondération par dimension.** Chaque dimension de $h_t$ a ses propres poids : la dimension « conflits ouverts » peut écouter surtout l'état narratif, la dimension « alliances » surtout le KG.
- **Une pondération contextuelle.** Les portes reçoivent aussi $U_z h_{t-1}$. L'importance d'une source dépend donc de ce que le modèle sait déjà : une nouvelle arête « ennemi de » compte davantage si elle touche un personnage impliqué dans un conflit ouvert.

Le GRU ne fait donc pas une moyenne fixe des sources. Il apprend **quand** et **pour quoi** chacune compte.

### 4.3 Trois décisions par chapitre

À chaque chapitre $t$, le GRU prend trois décisions, toutes apprises :

1. **Que relire du passé ?** $r_t$ décide quelles dimensions de $h_{t-1}$ servent à interpréter le chapitre.
2. **Quoi écrire ?** $\tilde h_t$ condense la nouveauté du chapitre, mise en contexte.
3. **Où écrire et où garder ?** $z_t$ décide, dimension par dimension, de conserver ou de remplacer.

### 4.4 Déroulé illustratif sur un arc

> Scénario fictif et comportement **attendu**, donné pour l'intuition. Ces comportements sont appris, pas programmés ; ils se vérifient avec les outils de la section 4.8.

| Chapitre | Ce qui se passe | Signal dominant dans $x_t$ | Comportement attendu des portes |
|---|---|---|---|
| $t_0$ | Arrivée sur une nouvelle île, nouveaux personnages | KG : nouveaux nœuds (personnages) ; état « arc : début » | $r$ bas et $z$ bas sur les dimensions « contexte local » : on réécrit ; $z \approx 1$ sur « équipage » |
| $t_0 + 3$ | Un antagoniste menace un allié | KG : nouvelle arête « menace » ; état : « conflit X ouvert » | $z$ bas sur les dimensions « conflits » : écriture ciblée |
| $t_0+4$ à $t_0+12$ | Combat en cours | événements « combat », état « conflit X : en cours » | $z$ élevé : la mémoire bouge peu, la prédiction reste « combat » ou « issue du combat » |
| $t_0 + 13$ | Révélation sur le passé d'un personnage | texte (flashback), événement « révélation » | écriture d'un fait durable sur des dimensions lentes |
| $t_0 + 20$ | Fin d'arc, départ de l'île | état « conflit X : résolu » | $r$ bas sur le local ; dimensions lentes intactes (alliances acquises, mystères ouverts) |

### 4.5 Du résumé $h_t$ à la prédiction (étape 8)

Un chapitre contient **plusieurs** événements. C'est donc un problème **multi-label** : une sigmoïde par type d'événement, pas un softmax.

$$
\hat p_{t+1} = \sigma\!\left(W_o\, h_t + b_o\right) \in [0, 1]^C,
\qquad
\mathcal{L} = \sum_{t} \mathrm{BCE}\!\left(\hat p_{t+1},\, y_{t+1}\right)
$$

- **Déséquilibre des classes** : utiliser `pos_weight` dans la BCE, ou une *focal loss* ; les événements rares (trahison, mort) sont les plus intéressants et les plus rares.
- **Top-K** : on trie $\hat p_{t+1}$ et on garde les $K$ premiers pour la Précision@K. Pour le F1, le seuil de décision se règle sur la **validation**, jamais sur le test.
- **Taxonomie** : une dizaine à une trentaine de types d'événements, pour avoir assez d'exemples positifs par classe.
- **Extensions utiles** :
  - *Connexion directe* : classifier sur $[h_t \,;\, x_t]$ pour que l'information du dernier chapitre n'ait pas à transiter par la mémoire.
  - *Attention sur le passé* : $c_t = \sum_{k \le t} \alpha_{t,k}\, h_k$, avec $\alpha_{t,k} = \mathrm{softmax}_k\big(q(h_t)^\top \kappa(h_k)\big)$, puis classifier sur $[h_t \,;\, c_t]$. Le modèle peut alors « aller rechercher » un chapitre lointain (rappel d'un indice) sans tout stocker dans $h_t$. La causalité est respectée, puisque $k \le t$.
  - *Événements avec participants* : pour prédire `combat(Luffy, ?)`, un score bilinéaire $\sigma\big(h_t^\top W_{\text{type}}\, e_{\text{entité}}\big)$, analogue à la prédiction de liens dans un KG.

### 4.6 Implémentation PyTorch (étapes 6 → 7 → 8)

```python
import torch
import torch.nn as nn
import torch.nn.functional as F


# ---------------------------------------------------------------------------
# Étape 6 — Fusion : chaque source est projetée dans un espace commun normalisé
# ---------------------------------------------------------------------------
class ModalityFusion(nn.Module):
    def __init__(self, in_dims: dict, d_mod: int = 128, p_modality_drop: float = 0.1):
        super().__init__()
        self.names = list(in_dims)
        self.proj = nn.ModuleDict({
            name: nn.Sequential(nn.Linear(d, d_mod), nn.LayerNorm(d_mod), nn.GELU())
            for name, d in in_dims.items()
        })
        self.p = p_modality_drop

    def forward(self, feats: dict, mask_modalities=()):
        blocks = []
        for name in self.names:
            e = self.proj[name](feats[name])                       # (B, T, d_mod)
            if name in mask_modalities:                             # ablation à l'inférence
                e = torch.zeros_like(e)
            elif self.training and self.p > 0:                      # « modality dropout »
                keep = (torch.rand(e.shape[0], 1, 1, device=e.device) > self.p).to(e.dtype)
                e = e * keep
            blocks.append(e)
        return torch.cat(blocks, dim=-1)                            # x_t = [e_texte ; e_evt ; e_kg ; e_etat]


# ---------------------------------------------------------------------------
# Initialisation « chrono » (adaptée de Tallec & Ollivier, 2018) à la convention PyTorch :
# z_t ≈ 1 ⇔ garder la mémoire.  σ(log u) = u / (1 + u)  ⇒  constante de temps initiale ≈ 1 + u.
# ---------------------------------------------------------------------------
@torch.no_grad()
def chrono_init_(gru: nn.GRU, t_max: int):
    H = gru.hidden_size
    for layer in range(gru.num_layers):
        b_ih = getattr(gru, f"bias_ih_l{layer}")
        b_hh = getattr(gru, f"bias_hh_l{layer}")
        u = torch.empty(H).uniform_(1.0, float(t_max - 1))
        b_ih[H:2 * H] = torch.log(u)        # tranche « z » de (b_ir | b_iz | b_in)
        b_hh[H:2 * H] = 0.0


# ---------------------------------------------------------------------------
# Étapes 6 → 7 → 8 : Fusion → GRU → Classifieur multi-label
# ---------------------------------------------------------------------------
class NarrativeGRU(nn.Module):
    def __init__(self, in_dims: dict, n_event_types: int, d_mod: int = 128,
                 d_h: int = 256, dropout: float = 0.2, chrono_tmax: int | None = 200):
        super().__init__()
        self.fusion = ModalityFusion(in_dims, d_mod)
        self.in_drop = nn.Dropout(dropout)
        # num_layers=1 : suffisant pour ~1 000 chapitres, et nécessaire pour le cache d'états ci-dessous.
        # Jamais bidirectional=True : le GRU lirait les chapitres futurs.
        self.gru = nn.GRU(d_mod * len(in_dims), d_h, num_layers=1, batch_first=True)
        self.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(d_h, n_event_types))
        if chrono_tmax:
            chrono_init_(self.gru, chrono_tmax)

    def forward(self, feats: dict, h0=None, mask_modalities=()):
        x = self.in_drop(self.fusion(feats, mask_modalities))      # (B, T, d_x)
        H, h_last = self.gru(x, h0)                                 # H[:, k] = h_{k+1}
        logits = self.head(H)                                       # logits[:, k] → événements du chapitre k+2
        return logits, H, h_last


# ---------------------------------------------------------------------------
# Entraînement : fenêtres aléatoires + état initial pris dans un cache (« stored state »)
# Convention d'indices (0-based) : feats[m][k] = chapitre k+1 ; Y[k] = événements du chapitre k+1.
# À la position k, h_{k+1} (lecture des chapitres 1..k+1) prédit Y[k+1].
# ---------------------------------------------------------------------------
@torch.no_grad()
def compute_state_cache(model, feats, T_end):
    """Fait lire au GRU les chapitres 1..T_end d'une traite (mode eval) et renvoie tous les h_k."""
    model.eval()
    _, H, _ = model({m: v[:T_end].unsqueeze(0) for m, v in feats.items()})
    return H[0]                                                     # (T_end, d_h)


def train_epoch(model, feats, Y, T_train, opt, pos_weight,
                window=64, batch_size=16, steps=20, clip=1.0):
    """T_train : nombre de chapitres d'entraînement (aucune cible au-delà de T_train)."""
    cache = compute_state_cache(model, feats, T_train)              # états « gelés » pour l'époque
    model.train()
    max_start = T_train - 1 - window                                 # dernière cible = Y[T_train-1]
    total = 0.0
    for _ in range(steps):
        starts = torch.randint(0, max_start + 1, (batch_size,))
        xb = {m: torch.stack([v[s:s + window] for s in starts]) for m, v in feats.items()}
        yb = torch.stack([Y[s + 1:s + window + 1] for s in starts])  # cibles décalées de +1 chapitre
        h0 = torch.stack([cache[s - 1] if s > 0 else torch.zeros_like(cache[0])
                          for s in starts]).unsqueeze(0)             # (1, B, d_h)
        logits, _, _ = model(xb, h0=h0)
        loss = F.binary_cross_entropy_with_logits(logits, yb, pos_weight=pos_weight)
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), clip)    # le GRU n'empêche pas l'explosion
        opt.step()
        total += loss.item()
    return total / steps


# ---------------------------------------------------------------------------
# Évaluation (étape 10) : Précision@K sur les chapitres cibles [a, b)
# ---------------------------------------------------------------------------
def precision_at_k(scores, Y_true, k=3):
    topk = scores.topk(k, dim=-1).indices
    hits = Y_true.gather(-1, topk).sum(-1)
    return (hits / k).mean().item()


@torch.no_grad()
def evaluate(model, feats, Y, a, b, k=3, mask_modalities=()):
    """Prédit les chapitres d'indice a..b-1 en lisant uniquement les chapitres qui précèdent chacun."""
    model.eval()
    logits, _, _ = model({m: v[:b - 1].unsqueeze(0) for m, v in feats.items()},
                         mask_modalities=mask_modalities)
    scores = logits[0, a - 1:b - 1]                                 # position k-1 → cible Y[k]
    return precision_at_k(scores, Y[a:b], k)


def baselines(Y, T_train, a, b, k=3):
    """Deux références à battre absolument."""
    prior = Y[:T_train].mean(0).expand(b - a, -1)                   # fréquence globale des événements
    persistence = Y[a - 1:b - 1] + 1e-3 * prior                     # « le chapitre t+1 ressemble au t »
    return {"prior": precision_at_k(prior, Y[a:b], k),
            "persistance": precision_at_k(persistence, Y[a:b], k)}
```

**Exemple d'utilisation** (données factices, pour vérifier les dimensions de bout en bout) :

```python
torch.manual_seed(0)
T, C = 1100, 20                                   # chapitres, types d'événements
Y = (torch.rand(T, C) < 0.15).float()            # Y[k] = événements du chapitre k+1 (étapes 3 et 9)
feats = {
    "texte":      torch.randn(T, 768),            # étape 1
    "evenements": Y.clone(),                      # étape 3 : événements du chapitre lui-même
    "kg":         torch.randn(T, 128),            # étape 4 : embedding de KG(t) (+ ΔKG)
    "etat":       torch.randn(T, 32),             # étape 5
}
T_train, T_val = 800, 950                         # découpage temporel strict

model = NarrativeGRU({m: v.shape[1] for m, v in feats.items()}, n_event_types=C)
pos = Y[:T_train].sum(0)
pos_weight = ((T_train - pos) / pos.clamp(min=1)).clamp(max=20)
opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-2)

for epoch in range(10):
    loss = train_epoch(model, feats, Y, T_train, opt, pos_weight)
print("P@3 validation :", evaluate(model, feats, Y, T_train, T_val))
print("Références     :", baselines(Y, T_train, T_train, T_val))
print("P@3 sans KG    :", evaluate(model, feats, Y, T_train, T_val, mask_modalities=("kg",)))
```

Sur ces données aléatoires, les scores n'ont évidemment aucun sens. L'exemple sert seulement à valider le câblage. Le code a aussi été testé sur une série synthétique de 1 100 « chapitres » avec arcs et événements différés : le modèle y bat les deux références, et un test confirme la **causalité** (modifier les chapitres futurs ne change aucune prédiction passée).

### 4.7 Recettes d'entraînement et hyperparamètres de départ

| Hyperparamètre | Valeur de départ | Justification |
|---|---|---|
| $d_h$ (taille de la mémoire) | 128 à 256 | assez pour une mémoire multi-échelle, sans sur-paramétrer |
| Couches GRU | 1 | peu de données ; ajouter une couche seulement si l'ablation le justifie |
| $d_{\text{mod}}$ par source | 64 à 128 | sources équilibrées dans $x_t$ |
| Dropout (entrée, sortie) | 0,2 à 0,3 | régularisation indispensable avec environ 1 000 exemples |
| *Modality dropout* | 0,1 | empêche de dépendre d'une seule source (souvent le texte) |
| Optimiseur | AdamW, lr $10^{-3}$, *weight decay* $10^{-2}$ | standard robuste |
| Écrêtage du gradient | norme 1,0 | le GRU n'empêche pas l'explosion |
| Fenêtre $W$ | 64 à 128 chapitres | couvre un arc typique |
| `chrono_tmax` | 100 à 300 | constantes de temps initiales à l'échelle des arcs |
| Arrêt précoce | sur la Précision@K de validation | jamais sur le test |
| Graines aléatoires | au moins 3 | avec si peu de données, la variance entre graines est forte |

### 4.8 Diagnostiquer ce que la mémoire a appris

1. **Tracer les portes.** Avec `GRUCellPyTorchStyle.from_nn_gru(model.gru)` (section 2.8), rejouer la série et tracer la moyenne de $z_t$ et $r_t$ par chapitre. On s'attend à des creux de $r_t$ aux débuts d'arc. Si ce n'est pas le cas, le modèle n'exploite pas la structure narrative.
2. **Ablation par source à l'inférence.** `evaluate(..., mask_modalities=("kg",))` mesure la perte de Précision@K quand une source est retirée, sans réentraîner.
3. **Attribution par bloc.** Gradient × entrée (ou *integrated gradients*) sur chaque bloc de $x_t$ pour une prédiction donnée : quelle source, et quels chapitres passés, ont poussé la prédiction ?
4. **Sondes linéaires sur $h_t$.** Entraîner un classifieur linéaire à retrouver un fait depuis $h_t$, par exemple « Zoro est-il dans l'équipage ? » ou « le conflit X est-il ouvert ? ». Si la sonde réussit 100 chapitres après le fait, la mémoire le retient vraiment.

### 4.9 Points de vigilance propres au projet : les fuites temporelles

Le schéma pose la règle « aucune information future après le chapitre $t$ ». Elle est facile à violer **sans le voir** :

- **Encodeurs et LLM pré-entraînés.** Un modèle de texte ou un extracteur de type LLM, entraîné sur le web, a pu lire des résumés de chapitres **postérieurs** à $t$. Il peut alors injecter une connaissance du futur, par exemple qualifier d'« allié » un personnage avant la révélation. Parade : consigne stricte (« n'utilise que ce texte »), exiger pour chaque relation du KG le chapitre source ($\le t$), et surtout **évaluer sur les chapitres publiés après la date de coupure des modèles utilisés**. C'est le seul jeu de test réellement propre.
- **Résumés rétrospectifs.** Les résumés de wiki sont parfois écrits avec le recul : vrai nom révélé plus tard, mention de ce qu'un personnage « deviendra ». À auditer sur un échantillon.
- **Construction du KG.** $KG(t)$ doit être construit **cumulativement**, uniquement à partir des chapitres $1..t$, jamais à partir de fiches de personnages à jour.
- **Prétraitements.** Normalisations, vocabulaire d'entités et taxonomie d'événements doivent être calculés **sur la période d'entraînement seulement**.
- **Erreurs corrélées** entre l'étape 3 (entrée) et l'étape 9 (cible) : voir section 3.2.3.

---

## 5. Ressources pour aller plus loin

### 5.1 Articles fondateurs (RNN, LSTM, GRU)

| Référence | Pourquoi la lire | Lien |
|---|---|---|
| Cho, van Merriënboer, Gulcehre, Bahdanau, Bougares, Schwenk, Bengio (2014). *Learning Phrase Representations using RNN Encoder–Decoder for Statistical Machine Translation.* EMNLP 2014 | **L'article originel du GRU** (l'unité cachée à portes de reset et de mise à jour) | [arXiv:1406.1078](https://arxiv.org/abs/1406.1078) |
| Chung, Gulcehre, Cho, Bengio (2014). *Empirical Evaluation of Gated Recurrent Neural Networks on Sequence Modeling* | Nomme le GRU et le compare au LSTM : performances comparables, toutes deux bien meilleures que le RNN simple | [arXiv:1412.3555](https://arxiv.org/abs/1412.3555) |
| Hochreiter, Schmidhuber (1997). *Long Short-Term Memory.* Neural Computation 9(8) | Le LSTM, ancêtre direct du GRU | [doi:10.1162/neco.1997.9.8.1735](https://doi.org/10.1162/neco.1997.9.8.1735) |
| Bengio, Simard, Frasconi (1994). *Learning Long-Term Dependencies with Gradient Descent is Difficult.* IEEE Trans. Neural Networks 5(2) | Analyse fondatrice de la disparition du gradient | [doi:10.1109/72.279181](https://doi.org/10.1109/72.279181) |
| Pascanu, Mikolov, Bengio (2013). *On the difficulty of training Recurrent Neural Networks.* ICML 2013 | Explosion / disparition du gradient ; origine de l'écrêtage par la norme | [arXiv:1211.5063](https://arxiv.org/abs/1211.5063) |
| Jozefowicz, Zaremba, Sutskever (2015). *An Empirical Exploration of Recurrent Network Architectures.* ICML 2015 | Plus de 10 000 architectures comparées ; pas de vainqueur universel ; biais d'oubli à 1 | [PMLR v37](https://proceedings.mlr.press/v37/jozefowicz15.html) |
| Tallec, Ollivier (2018). *Can recurrent neural networks warp time?* ICLR 2018 | Les portes vues comme des constantes de temps ; **initialisation chrono** | [arXiv:1804.11188](https://arxiv.org/abs/1804.11188) |
| El Hihi, Bengio (1995). *Hierarchical Recurrent Neural Networks for Long-Term Dependencies.* NIPS 1995 | Récurrence multi-échelle (piste « GRU par arc ») | [PDF NeurIPS](https://papers.nips.cc/paper_files/paper/1995/file/c667d53acd899a97a85de0c201ba99be-Paper.pdf) |

### 5.2 Graphes de connaissances et réseaux récurrents

| Référence | Lien avec notre pipeline | Lien |
|---|---|---|
| Li, Tarlow, Brockschmidt, Zemel (2016). *Gated Graph Sequence Neural Networks.* ICLR 2016 | Des unités récurrentes à portes **à l'intérieur** d'un GNN : piste pour encoder le KG (étape 4) | [arXiv:1511.05493](https://arxiv.org/abs/1511.05493) |
| Seo, Defferrard, Vandergheynst, Bresson (2016). *Structured Sequence Modeling with Graph Convolutional Recurrent Networks* | Combine convolution sur graphe et RNN pour des séquences de graphes | [arXiv:1612.07659](https://arxiv.org/abs/1612.07659) |
| Pareja et al. (2020). *EvolveGCN: Evolving Graph Convolutional Networks for Dynamic Graphs.* AAAI 2020 | Un RNN fait évoluer les **poids** du GCN au fil du temps ; adapté quand l'ensemble des personnages change | [arXiv:1902.10191](https://arxiv.org/abs/1902.10191) |
| Jin, Qu, Jin, Ren (2020). *Recurrent Event Network: Autoregressive Structure Inference over Temporal Knowledge Graphs.* EMNLP 2020 | **Le plus proche de notre problème** : prédire des événements futurs à partir d'une séquence de KG passés | [arXiv:1904.05530](https://arxiv.org/abs/1904.05530) |
| Li et al. (2021). *Temporal Knowledge Graph Reasoning Based on Evolutional Representation Learning* (RE-GCN). SIGIR 2021 | Modélise récurremment la séquence de KG pour prédire les faits futurs | [arXiv:2104.10353](https://arxiv.org/abs/2104.10353) |

### 5.3 Prédiction d'événements narratifs et suivi d'entités

| Référence | Lien avec notre pipeline | Lien |
|---|---|---|
| Chambers, Jurafsky (2008). *Unsupervised Learning of Narrative Event Chains.* ACL 2008 | Fondement des « chaînes d'événements narratifs » centrées sur un protagoniste | [ACL Anthology P08-1090](https://aclanthology.org/P08-1090/) |
| Pichotta, Mooney (2016). *Learning Statistical Scripts with LSTM Recurrent Neural Networks.* AAAI 2016 | Un RNN prédit les événements suivants d'un récit : notre étape 7, appliquée aux scripts | [doi:10.1609/aaai.v30i1.10347](https://doi.org/10.1609/aaai.v30i1.10347) |
| Li, Ding, Liu (2018). *Constructing Narrative Event Evolutionary Graph for Script Event Prediction.* IJCAI 2018 | Graphe d'événements + GNN pour prédire l'événement suivant | [arXiv:1805.05081](https://arxiv.org/abs/1805.05081) |
| Henaff, Weston, Szlam, Bordes, LeCun (2017). *Tracking the World State with Recurrent Entity Networks.* ICLR 2017 | Une mémoire récurrente à portes **par entité** : piste pour une mémoire par personnage | [arXiv:1612.03969](https://arxiv.org/abs/1612.03969) |

### 5.4 Cours, documentation et articles de blog

- **Dive into Deep Learning, §10.2 « Gated Recurrent Units (GRU) »** — équations, figures et implémentation from scratch, en PyTorch, JAX, TensorFlow et MXNet : <https://d2l.ai/chapter_recurrent-modern/gru.html>
- **Documentation PyTorch `torch.nn.GRU`** — équations exactes, formes des tenseurs, note sur la variante *reset-after* : <https://docs.pytorch.org/docs/stable/generated/torch.nn.GRU.html>
- **Chris Olah, « Understanding LSTM Networks » (2015)** — le diagramme de référence des portes ; la fin aborde le GRU : <https://colah.github.io/posts/2015-08-Understanding-LSTMs/>
- **Andrej Karpathy, « The Unreasonable Effectiveness of Recurrent Neural Networks » (2015)** — l'intuition de ce qu'un RNN apprend à mémoriser : <http://karpathy.github.io/2015/05/21/rnn-effectiveness/>
- **Michael Phi, « Illustrated Guide to LSTM's and GRU's: A step by step explanation »** — version écrite de la vidéo citée plus bas : <https://towardsdatascience.com/illustrated-guide-to-lstms-and-gru-sa-step-by-step-explanation-44e9eb85bf21>
- **Stanford CS224N (2025), cours 6 « LSTM RNNs and Neural Machine Translation »** — transparents sur la disparition du gradient : <https://web.stanford.edu/class/archive/cs/cs224n/cs224n.1254/slides_w25/cs224n-2025-lecture06-fancy-rnn.pdf>
- **MIT 6.S191 « Introduction to Deep Learning »** — cours 2 « Deep Sequence Modeling », vidéos et transparents mis à jour chaque année : <https://introtodeeplearning.com/>

### 5.5 Vidéos YouTube

Les liens « Recherche YouTube » pointent vers le titre exact de la vidéo.

| Vidéo | Chaîne | Pourquoi la regarder | Lien |
|---|---|---|---|
| *Recurrent Neural Networks (RNNs), Clearly Explained!!!* | StatQuest with Josh Starmer | Intuition du RNN, puis son défaut critique (gradients qui disparaissent ou explosent) qui motive les portes | [Recherche YouTube](https://www.youtube.com/results?search_query=StatQuest+Recurrent+Neural+Networks+RNNs+Clearly+Explained) |
| *Long Short-Term Memory (LSTM), Clearly Explained* | StatQuest with Josh Starmer | Les portes pas à pas, avec des nombres ; directement transposable au GRU (z = oubli + entrée fusionnées) | [Recherche YouTube](https://www.youtube.com/results?search_query=StatQuest+Long+Short-Term+Memory+LSTM+Clearly+Explained) |
| *Illustrated Guide to LSTM's and GRU's: A step by step explanation* (~11 min) | Michael Phi | Animations des deux cellules côte à côte, **GRU explicitement couvert** | [Recherche YouTube](https://www.youtube.com/results?search_query=Illustrated+Guide+to+LSTM%27s+and+GRU%27s+step+by+step+explanation) |
| *Gated Recurrent Unit (GRU) (C5W1L09)* | DeepLearningAI (Andrew Ng, cours *Sequence Models*) | Construction progressive du GRU. ⚠️ Notation inversée : chez Ng, $\Gamma_u \approx 1$ = écrire | [Recherche YouTube](https://www.youtube.com/results?search_query=Gated+Recurrent+Unit+GRU+C5W1L09) · [Leçon du cours](https://learn.deeplearning.ai/specializations/deep-learning/lesson/mhird/gated-recurrent-unit-(gru)) |
| *L19/6 Gated Recurrent Unit (GRU)* (~17 min) | Dive into Deep Learning (UC Berkeley STAT 157) | Le cours vidéo associé au manuel D2L | [Recherche YouTube](https://www.youtube.com/results?search_query=L19%2F6+Gated+Recurrent+Unit+GRU+d2l) |
| *Stanford CS224N (Winter 2019), Lecture 7 — Vanishing Gradients and Fancy RNNs* | Stanford Online | Le traitement le plus rigoureux de la disparition du gradient, puis LSTM et GRU | [YouTube](https://www.youtube.com/watch?v=QEw0qEa0E50) |
| *MIT 6.S191, Lecture 2 — Recurrent Neural Networks, Transformers, and Attention* | MIT 6.S191 (cours d'Ava Amini) | Vue d'ensemble moderne : RNN → portes → attention (utile pour l'extension « attention sur le passé ») | [Recherche YouTube](https://www.youtube.com/results?search_query=MIT+6.S191+Recurrent+Neural+Networks+Transformers+and+Attention) |
| Série *Neural Networks* — « Gradient descent, how neural networks learn », « What is backpropagation really doing? », « Backpropagation calculus » | 3Blue1Brown | L'intuition visuelle du gradient et de la rétropropagation, indispensable pour comprendre **pourquoi** il disparaît dans un RNN. La série ne traite pas des RNN ; ses épisodes sur l'attention et les transformers éclairent l'alternative | [« What is backpropagation really doing? »](https://www.youtube.com/watch?v=Ilg3gGewQ5U) · [Recherche série](https://www.youtube.com/results?search_query=3Blue1Brown+neural+networks+deep+learning+chapter) |

**Parcours conseillé** : 3Blue1Brown (gradient) → StatQuest RNN → StatQuest LSTM → Michael Phi (GRU) → section 2 de ce document → D2L §10.2 (code) → article de Cho et al. (2014) → RE-Net (Jin et al., 2020) pour le lien avec le Knowledge Graph.

---

### Glossaire FR / EN

| Français | Anglais | Où dans le document |
|---|---|---|
| porte de mise à jour | update gate ($z_t$) | 2.4 |
| porte de réinitialisation | reset gate ($r_t$) | 2.3 |
| état candidat | candidate hidden state ($\tilde h_t$) | 2.2 |
| état caché / mémoire | hidden state ($h_t$) | 2.5 |
| rétropropagation à travers le temps | backpropagation through time (BPTT) | 1.3, 2.7 |
| disparition / explosion du gradient | vanishing / exploding gradient | 1.3, 2.6 |
| écrêtage du gradient | gradient clipping | 1.6, 4.7 |
| fuite d'information temporelle | temporal leakage | 4.9 |