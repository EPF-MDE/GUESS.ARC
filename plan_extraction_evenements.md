# Extraction des événements : préparsing et appels au modèle local

> **Projet** : prédiction des événements du chapitre t+1 de *One Piece*.
> **Périmètre** : l'étape 3 (extraction des événements) et l'étape 9 (même outil, appliqué au chapitre t+1).
> **Données de départ** : dossier `silver/` (V0, 1 194 chapitres en `.md`) et entités V0 (`characters.json`, `devil_fruits.json`, `islands.json`).
> Tous les chiffres de ce document ont été mesurés sur ces fichiers.
> **Mise à jour du 2026-10-28** (issue #90) : les chiffres du préparsing (§2), des entités par chapitre (§3.2) et des tailles d'appel (§5.3) ont été recomptés sur la silver actuelle (1 196 chapitres, table des personnages séparée des notes, annotations d'apparition conservées). Le préparsing est implémenté dans `guess_arc.events` (`python -m guess_arc.events --dry-run`).

---

## 0. Les décisions en un coup d'œil

| Sujet | Décision | Pourquoi |
|---|---|---|
| Texte envoyé au modèle | numéro, titre, arc, Short Summary, Long Summary, Chapter Notes | décision de l'équipe |
| Infos personnages, lien vers le wiki, autres métadonnées | **retirées du texte envoyé**, mais la liste des personnages est **rangée à part** plutôt que jetée | elle sert à choisir les entités à envoyer et à produire des événements gratuits (section 2.4) |
| Appels | 1 appel par chapitre, 15 s d'attente entre deux appels, reprise automatique en cas d'arrêt | contrainte du serveur de l'école |
| Entités | **pas les 3 JSON en entier** : seulement les entités du chapitre, avec des champs « sans futur » | 313 000 tokens pour `characters.json` seul, et des informations de fin de série (section 3) |
| Schéma de sortie | **un type choisi dans une liste fermée + une description libre** | les étapes 8 et 10 ont besoin de classes comparables ; la description libre permet de changer la liste sans tout relancer (section 4) |
| Reproductibilité | température 0, graine fixe, prompt, schéma et modèle versionnés | la même extraction sert d'entrée (étape 3) et de vérité terrain (étape 9) |
| Modèle | **Gemma 4 26B A4B** (serveur de l'école), sans mode « thinking » au départ | rapide et assez capable pour la tâche ; réglages en section 5.4 |
| Serveur | **https://locallm.mde.epf.fr/**, accessible uniquement depuis le réseau de l'école | type de serveur et route à confirmer avec `test_serveur.py` (section 5.5) |

---

## 1. Vue d'ensemble

```text
silver/chapter_XXXX.md
        │
        ▼
(A) Préparsing ──────────────► clean/chapter_XXXX.json      (texte envoyé au modèle)
        │                      meta/chapter_XXXX.json       (liste des personnages, rangée à part)
        ▼
(B) Sélection des entités ───► entités du chapitre, champs « sans futur » uniquement
        │                      (à partir des 3 JSON + meta)
        ▼
(C) Construction de l'appel ─► prompt système + prompt utilisateur + schéma JSON
        │
        ▼
(D) Appel au modèle local ───► out/v1/chapter_XXXX.json + out/v1/raw/…
        │                      1 appel par chapitre, puis 15 s d'attente
        ▼
(E) Validation automatique ──► rapport : JSON valide ? preuve trouvée ? fuite du futur ?
```

Arborescence proposée :

```text
data/silver/                   # entrée actuelle (ne pas modifier)
data/clean/                    # sortie du préparsing (texte)
data/meta/                     # liste des personnages par chapitre (hors prompt)
data/entities/v0/              # characters.json, devil_fruits.json, islands.json
prompts/system_v1.txt
prompts/user_template_v1.txt
schemas/events_v1.json
out/events/v1/                 # 1 fichier JSON validé par chapitre
out/events/v1/raw/             # réponses brutes du modèle
logs/run_v1.jsonl              # 1 ligne par appel : durée, tokens, erreurs
```

---

## 2. Préparsing

### 2.1 Ce qu'on garde, ce qu'on retire

| Élément du fichier silver | Action | Remarque |
|---|---|---|
| `chapter` | **garder** (entier) | |
| `title` | **garder** | prendre celui de l'en-tête YAML, pas le titre `# Chapter …` |
| `arc` | **garder** | 33 arcs |
| `## Short Summary` | **garder** | ~84 mots en médiane |
| `## Long Summary` | **garder** | ~600 mots en médiane |
| `## Chapter Notes` | **garder, après nettoyage** | voir 2.2 |
| `characters`, `character_count` | retirer du texte, **ranger dans `meta/`** | voir 2.4 |
| `source` (lien wiki), `license` | retirer du texte | garder la mention **CC BY-SA** dans le README du jeu de données : la licence impose de créditer le wiki |
| `jname`, `revision_id`, `revised_at`, `complete` | retirer | `jname` est cassé dans 112 fichiers (`"{{Ruby"`) |

### 2.2 Nettoyages, dans cet ordre

L'ordre compte : l'étape 2 a besoin de la liste des personnages, donc il faut la faire **avant** de retirer l'en-tête.

1. **Lire l'en-tête YAML** et les sections `##`.
2. ~~**Retirer la liste des personnages collée à la fin des Chapter Notes.**~~ *Plus nécessaire : la silver actuelle range la table des personnages dans le front-matter, et ses Chapter Notes ne contiennent que des notes (9 326 au total, 7 par chapitre en médiane).* Texte d'origine : Le titre « Characters » s'est perdu au moment de l'extraction : dans 1 160 fichiers sur 1 194, les dernières puces des notes sont les noms de l'en-tête (« Gold Roger (flashback) », « Nami (cover) »). Règle : on retire une puce si son texte, une fois la parenthèse finale enlevée, est un nom de l'en-tête, ou si c'est une puce courte (6 mots ou moins) sans point final. Il reste environ **9 300 vraies notes**, 7 à 8 par chapitre en médiane.
3. **Retirer les notes éditoriales et les notes de couverture** : sur la silver actuelle, **95 notes éditoriales** (« This is the first/last chapter of the … Arc », début ou fin d'un acte, anime, éditions magazine ou volume, SBS) et **62 notes de couverture** (couverture, cover story, color spread, début ou fin d'une cover story désignée par son titre). La note entière est retirée : une dizaine de notes qui mêlent un fait du chapitre et une couverture (ch. 629, 909, 1138…) sont perdues, c'est assumé en v1. Il reste **9 169 notes**, 7 par chapitre en médiane.
4. **Repérer les fuites du futur** : 18 notes et 47 passages du Long Summary (recomptés sur la silver actuelle, après retrait des notes éditoriales et de couverture) qui parlent de la suite (« foreshadowing the events of the Punk Hazard and Wano Country arcs », « will later be corrected »…). On les repère avec une expression régulière, on les **relit à la main** (environ 65 cas, une heure), puis on retire la phrase ou le morceau de phrase concerné. On garde la trace de chaque suppression dans `flags`.
   ```text
   \b(would (later|eventually|go on to)|will later|later (be )?revealed|later in the series|
      in (a )?later chapters?|in the future|foreshadow\w*|(is|was) later)\b
   ```
5. **Normaliser le texte** : entités HTML (`html.unescape`), espaces insécables (`\xa0`) remplacées par des espaces normales, restes de balisage wiki (`[[`, `]]`, `{{…}}`), espaces multiples.
6. **Écrire** `clean/chapter_XXXX.json` et `meta/chapter_XXXX.json`.

### 2.3 Format de sortie du préparsing

`clean/chapter_0001.json` :

```json
{
  "chapter": 1,
  "title": "Romance Dawn —The Dawn of the Adventure—",
  "arc": "Romance Dawn Arc",
  "short_summary": "During his execution, the Pirate King Gold Roger revealed …",
  "long_summary": "Gold Roger held the title of \"Pirate King\" …",
  "chapter_notes": [
    "The previous Pirate King, Gold Roger, started the Great Pirate Era …",
    "Luffy eats the Gomu Gomu no Mi, believing it was a normal fruit …"
  ],
  "flags": { "meta_notes_removed": 1, "future_leaks_removed": 0 }
}
```

### 2.4 Le fichier `meta/` : pourquoi le garder

Ce fichier n'est **jamais envoyé tel quel** au modèle, mais il sert à deux choses :

1. **Choisir les entités à envoyer** pour ce chapitre (section 3.2), et fournir la liste des noms autorisés dans le schéma (section 4.4).
2. **Produire des événements sans IA** : première apparition (515 chapitres présentent au moins un nouveau personnage, à l'image ou en flashback), retour (règle redéfinie par arc dans la spec #88, à recompter avec #92), K.O. (388 annotations `ko`).

`meta/chapter_0001.json` :

```json
{
  "chapter": 1,
  "characters": [
    { "name": "Shanks", "mode": "on_panel" },
    { "name": "Gol D. Roger", "mode": "flashback" },
    { "name": "Nami", "mode": "cover" }
  ]
}
```

`mode` vient de l'annotation entre parenthèses : `on_panel` (aucune annotation), `flashback`, `cover`, `ko`, `image`, `mentioned`… Un personnage uniquement en `cover` (2 963 cas) ne participe pas au chapitre : il ne doit pas compter comme présent.

> ⚠️ Le champ `faction` de l'en-tête **n'est pas fiable**. C'est le sous-titre sous lequel le wiki range le personnage dans ce chapitre, et il change selon le contexte : Nami passe de « Straw Hat Pirates » à « Arlong Pirates » et revient, et on trouve des valeurs parasites comme « (Cover) », « Marine Ranks#Lieutenant » ou une valeur vide. Ne pas l'utiliser.

### 2.5 Contrôles automatiques après le préparsing

- 1 196 fichiers (ou plus avec le dossier à jour), numéros continus, aucun champ vide.
- Plus aucun nom de personnage isolé dans `chapter_notes`.
- Plus de `{{`, `[[` ni d'entité HTML dans le texte.
- Le nombre de notes par chapitre augmente fortement avec le temps (4 en médiane sur les 100 premiers chapitres, 10 sur les 100 derniers) : c'est normal, il ne faut pas le « corriger », mais il faudra en tenir compte (section 8).

---

## 3. Les entités (3 JSON, version V0)

### 3.1 Ce qu'ils contiennent

| Fichier | Entrées | Champs principaux |
|---|---|---|
| `characters.json` | 1 550 | name, first_appearance_arc (en fait un chapitre), race, status, description, journey, relationships, affiliation, epithet, devil_fruit, bounty, haki… |
| `devil_fruits.json` | 214 | name, english, type, subtype, user, description |
| `islands.json` | 164 | name, location, description, current_ruler, notable_locations, notable_members |

### 3.2 Problème 1 : la taille. On envoie seulement le sous-ensemble du chapitre

`characters.json` représente environ **313 000 tokens**, alors qu'un appel doit en faire quelques milliers. Pour chaque chapitre t, on envoie donc :

- **Personnages** : ceux de `meta/` dont le mode n'est pas seulement `cover`, plus ceux dont un nom ou alias apparaît dans le texte. Sans compter ceux du texte, il y en a 18 par chapitre en médiane, 78 au maximum.
- **Fruits du démon et îles** : seulement ceux dont le nom apparaît dans le texte du chapitre.
- **Filtre de temps** : seulement les personnages déjà apparus, c'est-à-dire avec une première apparition au chapitre t ou avant. `first_appearance_arc` contient « Chapter N » pour 1 420 entrées sur 1 550. Pour les autres (« SBS… », « Episode… », films), on garde l'entité seulement si elle figure dans `meta/` pour ce chapitre.

### 3.3 Problème 2 : les fiches décrivent la fin de l'histoire

Les fiches sont rédigées avec le recul. **Exemple avec la fiche de Luffy**, telle qu'elle serait envoyée au chapitre 1 :

- `devil_fruit` : « Hito Hito no Mi, Model: Nika (Awakened) », révélé au chapitre 1044 ;
- `bounty` : 3 000 000 000, atteint au chapitre 1053 ;
- `description` : « … Son of Dragon … », révélé au chapitre 432.

Le modèle risque alors d'écrire « Luffy, fils de Dragon » dans un événement du chapitre 10. La fuite contaminerait **à la fois les entrées (étape 3) et la vérité terrain (étape 9)**, et les scores deviendraient trompeurs.

Champs autorisés en V0 :

| Fichier | Envoyer | Ne pas envoyer |
|---|---|---|
| characters | `name`, alias (tirés des `[…]` et `(…)` du nom), `race` | `description`, `status`, `bounty`, `devil_fruit`, `haki`, `affiliation`, `epithet`, `relationships`, `origin`, `age`, `height` |
| characters, `journey` | seulement les étapes datées d'un chapitre ≤ t (40 % des étapes ont un chapitre) | les étapes sans chapitre |
| devil_fruits | `name`, `english`, si le nom apparaît dans le texte | `type` (celui de Luffy est passé de Paramecia à Zoan au ch. 1044), `user`, `description` |
| islands | `name`, `location` (la mer), si le nom apparaît dans le texte | `description`, `current_ruler`, `notable_members`, `notable_locations` |

Une fiche minimale fait environ 10 tokens, contre environ 140 pour une fiche complète. Même avec 80 personnages, le bloc entités reste sous les 1 500 tokens.

### 3.4 Problème 3 : les noms ne correspondent pas toujours

- 94 % des apparitions de personnages dans le silver correspondent à un nom de `characters.json`, une fois les crochets retirés.
- Les cas qui ne correspondent pas : « Franky » (stocké « Cutty Flam [Franky] »), « Kin'emon » (stocké « Kinemon »), « King » (« Arber [King] »), « Queen »…
- Il faut donc une **table d'alias** : nom canonique, puis noms entre `[…]` et `(…)`, puis normalisation (apostrophes, accents, casse). Dans le texte, les personnages sont souvent nommés par leur dernier mot (« Luffy », « Zoro », « Law ») : ajouter ce dernier mot comme alias quand il n'est pas ambigu.

### 3.5 Ce qu'il faudrait demander à l'équipe entités pour la V1

1. **Dater chaque information** avec le chapitre où elle est révélée : historique des primes, fruit (avec la date de révélation), changements d'affiliation, statut (décès), épithètes. On pourra alors envoyer des fiches complètes mais **coupées au chapitre t**.
2. **Utiliser les mêmes noms canoniques** que les pages de chapitre du wiki, et ajouter un champ `aliases`.
3. Convertir `first_appearance_arc` en un entier `first_appearance_chapter`.
4. Retirer le HTML des descriptions (`<strong>` dans 407 descriptions).

---

## 4. Le schéma JSON de sortie : mon avis

### 4.1 Pourquoi pas des événements entièrement libres

L'idée de ne pas définir d'événements précis est tentante, mais elle bloque la suite du pipeline :

- **Étape 8** : le classifieur prédit une probabilité par **type** d'événement. Il lui faut une liste de classes fixe.
- **Étape 10** : le F1 et la Précision@K comparent des prédictions à des vérités. « Luffy punches Kaido » et « Luffy fights Kaido » sont le même événement, mais deux textes libres ne se comparent pas.
- **Coût d'un changement** : avec 15 s d'attente obligatoire, un passage complet prend **10 à 25 heures** (section 5.7). Il vaut mieux bien choisir le schéma dès le départ.

### 4.2 Le compromis proposé

Chaque événement porte :

- un **`type` choisi dans une liste fermée** de 17 types, dont `other` pour ce qui n'entre nulle part ;
- une **`description` libre**, en une phrase.

Si la liste des types change plus tard, on peut **reclasser les descriptions sans rappeler le modèle**. Si `other` dépasse 15 % des événements, c'est le signe qu'il manque un type.

### 4.3 Les types d'événements

| Code | Signification |
|---|---|
| `combat` | affrontement physique entre personnages ou groupes |
| `defeat` | un personnage est vaincu, mis K.O. ou contraint d'abandonner |
| `death` | mort d'un personnage |
| `injury` | blessure grave |
| `capture` | capture, emprisonnement, enlèvement |
| `escape_rescue` | évasion, libération, sauvetage |
| `recruitment` | un personnage rejoint un équipage ou un groupe |
| `departure` | départ, séparation, quitte un lieu ou un groupe |
| `arrival` | arrivée sur une île ou dans un nouveau lieu |
| `alliance` | alliance, accord, coopération |
| `betrayal` | trahison |
| `revelation` | révélation d'une identité, d'un passé ou d'un secret |
| `power_reveal` | pouvoir, fruit du démon, Haki ou technique montré pour la première fois |
| `reunion` | retrouvailles |
| `status_change` | nouvelle prime, nouveau titre, nouveau rang |
| `declaration` | objectif, promesse, plan, déclaration de guerre |
| `other` | autre (à décrire dans `description`) |

Les flashbacks ne sont pas un type : chaque événement porte un champ `in_flashback` (vrai ou faux). Ainsi, l'exécution de Roger racontée au chapitre 1 n'est pas comptée comme un événement présent.

Les premières apparitions, retours après une longue absence et K.O. annotés sont produits **sans le modèle**, à partir de `meta/` (section 2.4).

### 4.4 Le schéma complet

`__NOMS_AUTORISES__` est remplacé, **à chaque appel**, par la liste des noms d'entités envoyés pour ce chapitre. Le modèle ne peut donc pas inventer de participant : un personnage absent de la liste va dans `unlisted_entities`, ce qui sert aussi de retour pour l'équipe entités.

```json
{
  "type": "object",
  "properties": {
    "chapter": { "type": "integer" },
    "events": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "evidence": { "type": "string" },
          "type": {
            "type": "string",
            "enum": ["combat", "defeat", "death", "injury", "capture", "escape_rescue",
                     "recruitment", "departure", "arrival", "alliance", "betrayal",
                     "revelation", "power_reveal", "reunion", "status_change",
                     "declaration", "other"]
          },
          "description": { "type": "string" },
          "participants": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "name": { "type": "string", "enum": ["__NOMS_AUTORISES__"] },
                "role": { "type": "string", "enum": ["agent", "target", "other"] }
              },
              "required": ["name", "role"],
              "additionalProperties": false
            }
          },
          "location": { "type": "string" },
          "status": { "type": "string", "enum": ["single", "start", "ongoing", "end"] },
          "in_flashback": { "type": "boolean" },
          "source": { "type": "string", "enum": ["long_summary", "short_summary", "chapter_notes"] }
        },
        "required": ["evidence", "type", "description", "participants", "location", "status",
                     "in_flashback", "source"],
        "additionalProperties": false
      }
    },
    "unlisted_entities": { "type": "array", "items": { "type": "string" } }
  },
  "required": ["chapter", "events", "unlisted_entities"],
  "additionalProperties": false
}
```

Quelques précisions :

- `location` vaut `""` si le lieu est inconnu. On évite le type `null`, que certains serveurs gèrent mal dans un schéma contraint.
- `status` sert pour les événements qui durent plusieurs chapitres : un combat commence (`start`), continue (`ongoing`) ou se termine (`end`).
- `evidence` est un passage **copié mot pour mot** du texte du chapitre. Le contrôle automatique vérifie qu'il y figure bien (section 6).
- **`evidence` est volontairement le premier champ.** Avec une sortie contrainte, le modèle écrit les champs dans l'ordre du schéma. En recopiant d'abord le passage, il classe ensuite à partir du texte plutôt que de sa mémoire de One Piece. Ne pas changer cet ordre.
- Le schéma n'utilise que `type`, `enum`, `required` et `additionalProperties`, les mots-clés les mieux pris en charge par les serveurs locaux. Éviter `maxLength`, `pattern` ou `minItems` tant que le serveur n'a pas été testé.

---

## 5. Les appels au modèle

### 5.1 Prompt système (`prompts/system_v1.txt`)

En anglais, comme les textes : les modèles extraient mieux dans la langue du texte.

```text
You are an information extraction system. You read the summary of ONE chapter of the
manga One Piece and list the narrative events that happen IN THIS CHAPTER.

Rules:
1. Use ONLY the chapter text provided. Do not use your own knowledge of One Piece.
   Never mention anything that has not happened yet at this chapter.
2. One event = one fact. Use the LONG SUMMARY as your main source. Use the Short Summary
   and the Chapter Notes only to check that you missed nothing: the same fact often
   appears in all three sections, so list it only once.
3. "type": choose exactly one type from the list below. Use "other" only if none fits.
4. "participants": use only names from the ENTITIES list, written exactly as listed.
   If a character involved is not in the list, add their name to "unlisted_entities".
5. "evidence": write it FIRST. Copy a short passage (at most 20 words) WORD FOR WORD
   from the chapter text that supports the event. Do not rephrase it.
6. "status": for events lasting several chapters (fights, captures…), say whether the
   event starts, continues or ends in this chapter. Otherwise use "single".
7. "in_flashback": true if the event is shown in a flashback or a story about the past.
8. "description": one short sentence in English, present tense, at most 25 words.
9. Output only JSON matching the schema.

Event types:
- combat: a physical fight between characters or groups
- defeat: a character is defeated, knocked out or forced to give up
- death: a character dies
- injury: a character is seriously injured
- capture: a character is captured, imprisoned or kidnapped
- escape_rescue: a character escapes, is freed or is rescued
- recruitment: a character joins a crew or a group
- departure: a character leaves a place or a group, or characters separate
- arrival: characters arrive on an island or in a new place
- alliance: characters ally, agree or cooperate
- betrayal: a character betrays another
- revelation: an identity, a past or a secret is revealed
- power_reveal: a power, Devil Fruit, Haki or technique is shown for the first time
- reunion: characters meet again after a separation
- status_change: a new bounty, title or rank
- declaration: a goal, promise, plan or declaration of war is stated
- other: any other notable event

Example of a correct output for a short chapter:
{exemple complet : le texte d'un chapitre court suivi de sa sortie JSON attendue,
 environ 500 tokens, pris parmi les chapitres qui ne sont PAS dans le jeu de référence}
```

> Le prompt système ne commence **pas** par `<|think|>` : c'est ce jeton qui active le mode « thinking » de Gemma 4 (section 5.4).

### 5.2 Prompt utilisateur (`prompts/user_template_v1.txt`)

```text
CHAPTER {chapter} — "{title}" — Arc: {arc}

ENTITIES (use these exact names):
Characters:
{une ligne par personnage : "- Monkey D. Luffy (aliases: Luffy; race: Human)"}
Devil Fruits mentioned:
{une ligne par fruit : "- Bara Bara no Mi (Chop-Chop Fruit)", ou "- none"}
Places mentioned:
{une ligne par île : "- Dawn Island (East Blue)", ou "- none"}

=== SHORT SUMMARY ===
{short_summary}

=== LONG SUMMARY ===
{long_summary}

=== CHAPTER NOTES ===
{une note par ligne, précédée de "- "}
```

### 5.3 Paramètres de l'appel

| Paramètre | Valeur | Pourquoi |
|---|---|---|
| température | 0 | même entrée, même sortie |
| graine (`seed`) | fixe, par exemple 42 | reproductibilité, si le serveur la prend en charge |
| sortie contrainte | le schéma de 4.4 | JSON toujours valide |
| longueur maximale de la réponse | 3 000 tokens | environ 25 événements |
| taille de contexte | **au moins 16 000 tokens** | un appel fait 4 000 à 5 000 tokens en médiane, jusqu'à environ 9 000 |
| délai d'expiration | 10 minutes | les chapitres longs sur un serveur chargé |

Taille d'un appel, d'après les données :

| Partie | Médiane | Maximum |
|---|---|---|
| texte du chapitre (prompt utilisateur sans entités, `data/event/in/`) | ~830 mots, soit ~1 150 tokens | ~2 460 mots (ch. 612), soit ~3 400 tokens |
| bloc entités (fiches minimales) | ~300 tokens | ~1 500 tokens |
| prompt système + schéma | ~1 500 tokens | ~1 500 tokens |
| réponse | ~1 000 tokens | ~3 000 tokens |

> ⚠️ **Avec Ollama**, la taille de contexte par défaut est petite (selon la version, quelques milliers de tokens) et le texte trop long est **tronqué sans message d'erreur**. Toujours fixer `num_ctx` explicitement.

### 5.4 Spécificités de Gemma 4 26B A4B

Le modèle de l'école est **Gemma 4 26B A4B** : un modèle « mixture of experts » de 25,2 milliards de paramètres, dont 3,8 milliards seulement servent pour chaque token. Il garde la mémoire d'un gros modèle avec une vitesse proche d'un petit.

| Point | Réglage | Pourquoi |
|---|---|---|
| Contexte | 256 000 tokens possibles | largement assez (un appel fait au plus ~9 000 tokens). Vérifier que le serveur n'est pas configuré plus bas |
| Mode « thinking » | **désactivé au départ** (pas de `<|think|>` en tête du prompt système) | plus rapide, et pas de conflit avec la sortie JSON contrainte. À tester en option sur le pilote, s'il reste des doublons ou des erreurs de type |
| Bloc de réflexion vide | même désactivé, Gemma 4 émet un bloc de réflexion vide ; vérifier au pilote que le serveur le retire avant le JSON | sinon le contenu n'est pas du JSON pur. Le client peut aussi l'enlever avant le parsing |
| Température | **0** (au lieu des valeurs conseillées par Google : 1,0, top_p 0,95, top_k 64) | ces valeurs visent la conversation ; ici on veut des sorties reproductibles |
| Boucles de répétition | surveiller les événements répétés à l'identique jusqu'à la limite de tokens | défaut possible avec la température 0. Si ça arrive : température 0,2 avec graine fixe, et dédoublonnage dans la validation |
| Connaissance de One Piece | le modèle a très probablement lu le wiki | d'où la preuve en premier, les participants fermés et le détecteur de fuites |

### 5.5 Le serveur de l'école : deux cas possibles

Adresse : **https://locallm.mde.epf.fr/** (`BASE_URL` dans le code). Le serveur n'est joignable que depuis le réseau de l'école : tous les tests et le passage complet doivent tourner depuis une machine de l'école.

**Première chose à faire sur place** : lancer `test_serveur.py`. En environ 3 minutes, il identifie le logiciel (Open WebUI, Ollama ou serveur compatible OpenAI), l'identifiant exact de Gemma 4 26B, la route qui applique vraiment le schéma JSON et celle qui accepte un appel d'environ 10 000 tokens sans le couper. Il écrit le résultat dans `diagnostic_serveur.json`.

Si c'est **Open WebUI** (fréquent dans les écoles) :
- la clé API se crée dans **Settings > Account > API keys**, et l'administrateur doit parfois autoriser les clés pour les étudiants ;
- elle s'envoie dans l'en-tête `Authorization: Bearer <clé>` ;
- les routes correspondant aux deux cas ci-dessous sont `/api/chat/completions` (cas 1) et `/ollama/api/chat` (cas 2). La route Ollama est probablement la bonne, car elle permet de passer le schéma (`format`) et de fixer `num_ctx`.

**Cas 1 : serveur compatible OpenAI** (vLLM, LM Studio, llama.cpp, et aussi Ollama via `/v1`) :

```python
payload = {
    "model": MODEL,
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ],
    "temperature": 0,
    "seed": 42,
    "max_tokens": 3000,
    "response_format": {
        "type": "json_schema",
        "json_schema": {"name": "chapter_events", "schema": schema, "strict": True},
    },
}
r = requests.post(f"{BASE_URL}/v1/chat/completions", json=payload, timeout=600)
content = r.json()["choices"][0]["message"]["content"]
```

**Cas 2 : API native d'Ollama** :

```python
payload = {
    "model": MODEL,
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ],
    "format": schema,                 # le schéma JSON va ici
    "stream": False,
    "options": {"temperature": 0, "seed": 42, "num_ctx": 16384, "num_predict": 3000},
}
r = requests.post(f"{BASE_URL}/api/chat", json=payload, timeout=600)
content = r.json()["message"]["content"]
```

### 5.6 La boucle

```python
for ch in chapters:                               # dans l'ordre : 1, 2, 3…
    out_file = OUT_DIR / f"chapter_{ch:04d}.json"
    if out_file.exists():                         # reprise : déjà traité
        continue

    entities = select_entities(ch)                # section 3.2 et 3.3
    schema = build_schema(allowed_names=entities.names)
    user_prompt = build_user_prompt(ch, entities)

    for attempt in range(3):
        raw = call_model(SYSTEM_PROMPT, user_prompt, schema)
        save_raw(ch, attempt, raw)                # on garde toutes les réponses brutes
        errors = validate(raw, schema, ch)        # section 6
        if not errors:
            break
        time.sleep(15)                            # la pause vaut aussi entre deux essais

    save_result(out_file, raw, errors, meta={
        "model": MODEL, "prompt_version": "v1", "schema_version": "v1",
        "date": now(), "attempts": attempt + 1,
    })
    log(ch, duration, tokens, errors)
    time.sleep(15)                                # 15 s entre deux chapitres
```

Points importants :

- **Reprise** : un chapitre déjà traité est sauté. On peut arrêter et relancer à tout moment.
- **Réponses brutes** : toujours sauvegardées, pour pouvoir analyser une erreur sans refaire l'appel.
- **Versions** : chaque sortie note le modèle, le prompt et le schéma utilisés.
- **Règle d'or** : si le modèle, le prompt ou le schéma changent, on **relance tous les chapitres**. Les étapes 3 et 9 doivent utiliser exactement la même extraction.

### 5.7 Durée d'un passage complet

1 196 chapitres × (15 s d'attente + temps de réponse du modèle) :

| Temps de réponse par chapitre | Durée totale |
|---|---|
| 15 s | ~10 h |
| 30 s | ~15 h |
| 60 s | ~25 h |

D'où l'intérêt de la reprise automatique, et de bien tester avant le passage complet (section 7).

---

## 6. Validation automatique des sorties

Pour chaque chapitre :

1. **JSON valide et conforme au schéma** (bibliothèque `jsonschema`).
2. **Preuve vérifiée** : `evidence` figure dans le texte du chapitre, après normalisation des espaces et des guillemets. Sinon, l'événement est signalé comme probablement inventé.
3. **Participants autorisés** : tous dans la liste du chapitre. Le schéma le garantit si le serveur l'applique, mais on revérifie.
4. **Détecteur de fuite du futur** : un nom cité dans `description` ou `unlisted_entities` qui n'apparaît qu'après le chapitre t (d'après `characters.json`) est signalé. On cherche aussi « later », « will », « future » dans les descriptions.
5. **Statistiques globales** :
   - nombre d'événements par chapitre et par époque ;
   - part de chaque type, et part de `other` (alerte au-delà de 15 %) ;
   - taux d'erreurs et de nouvelles tentatives.

---

## 7. Plan de test avant le passage complet

1. **Lancer `test_serveur.py` depuis le réseau de l'école**, puis poser au responsable du serveur les questions qui restent :
   - type de serveur (compatible OpenAI ? Ollama ?) ;
   - nom exact du modèle et taille de contexte maximale ;
   - prise en charge d'une sortie contrainte par schéma JSON ;
   - la règle des 15 s compte-t-elle à partir de la fin de la réponse ou du début de l'appel ? ;
   - créneaux autorisés pour un passage long (nuits, week-ends).
2. **Pilote sur 5 chapitres** pris à des époques différentes : relecture complète à la main, ajustement du prompt.
3. **Jeu de référence de 50 chapitres**, environ 10 par tranche de 200 chapitres, annoté à la main par vous deux, dont 10 chapitres en commun pour mesurer votre accord. On mesure :
   - précision, rappel et F1 par type ;
   - exactitude des participants ;
   - part des preuves retrouvées dans le texte ;
   - part de JSON valides.
   Seuils à atteindre avant de lancer le passage complet (propositions à ajuster en équipe) :

   | Critère | Objectif |
   |---|---|
   | JSON valide | au moins 99 % (garanti par le schéma si le serveur l'applique) |
   | Preuves retrouvées mot pour mot dans le texte | au moins 90 % |
   | F1 sur les types | au moins 0,7 |
   | Participants corrects | au moins 85 % |
   | Fuites du futur signalées | presque 0 |

   Si Gemma 4 26B A4B n'atteint pas ces seuils, essayer dans cet ordre :
   1. activer le mode « thinking » (`<|think|>`) sur le pilote et comparer ;
   2. ajouter un deuxième exemple complet dans le prompt système ;
   3. ne traiter que les Chapter Notes (phrases courtes, un fait par phrase), puis compléter avec le Long Summary ;
   4. faire passer les 50 chapitres de référence par un modèle d'API (quelques centimes) pour savoir si l'écart vient du modèle ou des consignes.
4. **Gel de la version** : prompt v1, schéma v1, modèle fixé.
5. **Passage complet**, avec reprise automatique.
6. **Contrôle qualité** : statistiques de la section 6, relecture d'un échantillon par arc, relance des chapitres en erreur.

> Le style du wiki change fortement avec le temps : 4 notes par chapitre au début, 10 sur les derniers chapitres, et des résumés deux fois plus longs (Long Summary : ~365 mots en médiane sur les 200 premiers chapitres, ~710 sur les 200 derniers). Les chapitres récents auront donc plus d'événements extraits. Pour l'étape 8, mieux vaut prédire la **présence** de chaque type (oui ou non) plutôt qu'un nombre d'événements, et vérifier les fréquences par époque.

---

## 8. Liste des tâches

**Préparsing**
- [x] Lire l'en-tête et les sections `##` (#90)
- [x] ~~Retirer la liste des personnages des Chapter Notes~~ (plus nécessaire)
- [x] Retirer les notes éditoriales et de couverture (#90)
- [ ] Repérer et relire les fuites du futur (environ 70 cas)
- [x] Normaliser le texte (HTML, espaces insécables, balisage wiki) (#90)
- [ ] Écrire `clean/` et `meta/`, puis lancer les contrôles de 2.5

**Entités**
- [ ] Table d'alias (crochets, parenthèses, dernier mot, normalisation)
- [ ] Filtre de temps par première apparition
- [ ] Fiches minimales « sans futur » (section 3.3)
- [ ] Envoyer à l'équipe entités les demandes de 3.5

**Appels au modèle**
- [ ] Lancer `test_serveur.py` depuis le réseau de l'école et garder `diagnostic_serveur.json`
- [ ] Obtenir les réponses du responsable du serveur (section 7, étape 1)
- [ ] Écrire le prompt système, le modèle de prompt utilisateur et le schéma v1
- [ ] Client API, avec reprise, sauvegarde des réponses brutes, journal et pause de 15 s
- [ ] Validation automatique (section 6)

**Évaluation**
- [ ] Pilote sur 5 chapitres
- [ ] Annotation des 50 chapitres de référence et mesure de l'accord entre vous deux
- [ ] Gel de la v1, passage complet, contrôle qualité
- [ ] Événements gratuits depuis `meta/` : première apparition, retour, K.O.
