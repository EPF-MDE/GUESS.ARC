# Extraction des entités : ce qu'on a construit, ce qu'on a obtenu, ce qu'on a appris

*English version: [entity-extraction.md](entity-extraction.md)*

- **Périmètre :** l'étape d'extraction des entités, tickets ENT-01 à ENT-08 (#80–#87), PR #104, et les correctifs #105 et #106
- **État décrit :** branche `extraction/entities`, commit `7b88730`, exécution sur le corpus complet le 10 novembre 2026
- **Public :** toute personne qui veut comprendre l'étape sans lire le code : l'équipe, le client, le jury

Les termes du domaine (Entity, Alias, Registry(t)...) restent en anglais, comme dans
[CONTEXT.md](../CONTEXT.md) et dans le code.

---

## 1. En bref

Pour chaque chapitre t de *One Piece*, on sait maintenant **quelles choses nommées le lecteur a déjà
rencontrées** (personnages, équipages, lieux, navires, fruits du démon, armes, objets), **sous quels
noms**, et **combien de fois elles ont été mentionnées**. Cette liste s'appelle **Registry(t)**.

On la construit sans qu'aucun modèle d'IA ne devine de noms. On réutilise le travail déjà fait par
les contributeurs du wiki : chaque lien `[[...]]` d'un résumé de chapitre pointe vers la page exacte
de ce qu'il nomme. Le titre de cette page devient l'identifiant unique de la chose.

| Quoi | Résultat |
|---|---|
| Chapitres couverts | 1 à 1193, tous |
| Entities distinctes | 2 534 |
| Mentions trouvées | 67 923 (22 321 par les liens, 45 602 retrouvées par recherche de noms) |
| Entities sans type (`Unknown`) | 1,35 % des Mentions |
| Proxy de précision (les noms retrouvés sont-ils vraiment dans le chapitre ?) | **97,8 %**, objectif ≥ 80 % |
| Proxy de rappel (trouve-t-on tous les personnages présents ?) | **53,9 %**, objectif ≥ 95 %, voir §6.1 : surtout une limite du texte source, pas de l'extracteur |
| Tests automatiques | 116, tous verts, sans réseau |

**Deux points restent ouverts :** le rappel faible (§6.1) et la relecture humaine des identités
cachées (§9, point 2).

---

## 2. Pourquoi cette étape existe

Le projet cherche à prédire quels personnages apparaîtront au chapitre n+1 à partir des chapitres 1
à n. Le modèle (un GRU, un modèle de séquences) a besoin, pour chaque chapitre, d'une liste propre de
ce qu'il contient. « Luffy », « Straw Hat » et « Monkey D. Luffy » doivent compter pour un seul
personnage, et « Fake Luffy » pour un autre.

Une règle structure toute l'étape (elle est écrite dans
l'[ADR 0002](adr/0002-reader-knowledge-only.md)) :

> **Au chapitre t, le modèle ne peut savoir que ce qu'un lecteur sait au chapitre t.**

Si les données d'entrée contiennent une information du futur (une identité secrète révélée 300
chapitres plus tard, un surnom donné plus tard), les scores du modèle paraissent bons en test mais
s'effondrent en conditions réelles, où le futur n'est pas disponible.

---

## 3. Le vocabulaire en une minute

Le glossaire complet est dans [CONTEXT.md](../CONTEXT.md). Les mots utilisés dans ce document :

| Mot | Sens | Exemple |
|---|---|---|
| **Entity** | Un être, un groupe, un lieu ou une chose nommée de l'histoire | Luffy, les Straw Hat Pirates, Wano Country |
| **Canonical name** | Le titre de la page du wiki anglais de l'Entity : son identifiant unique | `Edward Newgate` |
| **Alias** | Tout autre nom utilisé pour elle dans le texte | « Whitebeard » |
| **Scene** | Un paragraphe du Long Summary d'un chapitre | |
| **Mention** | Une occurrence d'une Entity dans une Scene | |
| **Cast** | Les personnages listés comme présents dans la table des personnages du chapitre (CharTable) | |
| **Entity type** | Une catégorie unique et fixe par Entity | Character, Group, Place, Ship, Devil Fruit, Weapon, Object, Unknown |
| **Title / Concept** | Un rang ou une notion générale. **Jamais** une Entity | Admiral, Pirate, Haki |
| **Disguise** | Une fausse identité présentée au lecteur comme une autre personne, jusqu'au chapitre de **Revelation** | Kyoshiro est en réalité Denjiro |
| **Registry(t)** | Toutes les Entities connues au chapitre t, avec leur type et les Aliases déjà utilisés | |

---

## 4. La première tentative, et pourquoi on l'a abandonnée

En septembre 2026, la première version essayait de **deviner** les entités à partir du texte brut :

1. spaCy (un outil généraliste de traitement du langage) repérait les noms dans les résumés et
   devinait leur nature (personne, lieu...).
2. Un modèle d'embedding transformait chaque nom en vecteur, puis un algorithme de clustering
   (HDBSCAN) regroupait les noms « qui se ressemblent » en une seule entité.

Cela fonctionnait mal, pour des raisons propres au domaine :

- **spaCy n'a jamais vu de noms de One Piece.** Il étiquetait *Zoro* et *Katakuri* comme des lieux,
  parce que des mots courts à consonance japonaise ressemblent pour lui à des noms de lieux. *Kaido*
  aussi était classé comme lieu.
- **Le clustering fusionnait des noms sans rapport.** Les vecteurs capturent l'apparence d'un nom,
  pas son sens. *Ohara* se retrouvait fusionné avec 45 noms sans rapport, et six royaumes différents
  avec un seul.
- **La détection d'objets attrapait le propriétaire.** « Zoro's sword » produisait un objet nommé
  « Zoro ». Sur le corpus complet, 54 % des « objets » détectés étaient en fait des noms de
  personnages.

Chaque correctif (chercher les noms sur le wiki, reclasser avec les catégories du wiki, retirer les
possessifs) allait dans la même direction : **le wiki connaît déjà la réponse.** En octobre, on a
aussi mesuré que faire annoter tous les chapitres par des API de LLM gratuites ne passait pas à
l'échelle (environ 5 000 à 7 000 tokens par chapitre, et des quotas de quelques dizaines de requêtes
par jour).

**Décision (26 octobre) :** abandonner la chaîne qui devinait, et ses lourdes dépendances, et
reconstruire l'extraction sur les liens du wiki, avec des règles fixes et lisibles.

---

## 5. Comment fonctionne l'extraction aujourd'hui

```text
 bronze (wikitexte brut des 1193 chapitres)
   │
   ├─ 1. Long Summary       ──► Scenes (une par paragraphe)
   ├─ 2. [[liens]]          ──► Mentions + Aliases datés
   ├─ 3. recherche de noms  ──► Mentions que le wiki n'a pas liées
   ├─ 4. CharTable          ──► Cast (qui est présent)
   ├─ 5. typage             ──► un Entity type par Entity
   ├─ 6. filtrage           ──► Titles et Concepts retirés
   └─ 7. Disguises          ──► identités cachées tenues à part jusqu'à leur Revelation
   │
 gold/entities : registry.jsonl  +  registry_quality.json  +  disguise_candidates.csv
```

Tout cela tient dans **une seule fonction**, `extract_entities(chapters, reference)`, dans
`src/guess_arc/entities/extraction.py`. Elle ne lit rien sur le disque et ne fait aucun appel
réseau : elle reçoit des données et renvoie un résultat. Tout ce qui touche aux fichiers ou au wiki
reste dans `pipeline.py`. C'est pour cela que les 116 tests tournent en une seconde environ, hors
ligne.

### Étape 1 : les Scenes

Chaque paragraphe du Long Summary d'un chapitre est une Scene. Les sous-titres, les titres en gras
et les images seules n'en sont pas.

### Étape 2 : les liens donnent les Mentions et les Aliases

Sur le wiki, `[[Edward Newgate|Whitebeard]]` affiche « Whitebeard » et pointe vers la page
*Edward Newgate*. On obtient donc, gratuitement et sans deviner :

- une **Mention** de `Edward Newgate` ;
- un **Alias**, « Whitebeard », **daté** par le premier chapitre où il est utilisé. Avant ce
  chapitre, l'Alias n'existe pas dans Registry(t). Par exemple, « Lucy » n'est pas un Alias de Sabo
  avant l'arc Dressrosa.

Tout texte de lien n'est pas un nom : `[[Marshall D. Teach|man]]`, `[[Kouzuki Hiyori|his daughter]]`.
Le texte ne devient un Alias que s'il commence par une majuscule et que son premier mot n'est pas
dans une liste de mots courants (`common_words.txt`).

Un lien vers une partie de page nomme en général cette partie :
`[[Gomu Gomu no Mi/Gear 5 Techniques|Gear 5]]` compte comme une Mention de la page parente,
*Gomu Gomu no Mi*, et ne crée jamais d'Alias. Deux sortes de liens font exception (#106), et les
catégories du wiki permettent de les reconnaître :

- **Une sous-page qui est une chose à part.** Les six satellites de Vegapunk sont des sous-pages de
  *Vegapunk* (`Vegapunk/Lilith`), mais chaque sous-page a ses propres catégories (*Female
  Characters*, *Satellites*). Quand les catégories d'une sous-page donnent un Entity type, c'est une
  Entity à part entière, nommée par son titre complet : `[[Vegapunk/Lilith|Lilith]]` est une Mention
  de `Vegapunk/Lilith` (Character) avec l'Alias « Lilith ». Une sous-page sans catégorie
  (`Haki/Armament Haki`) reste une partie de sa page parente.
- **Une entrée de catalogue.** *Animal Species*, *Plant and Fungi Species* et *Foods* sont des pages
  de liste (catégorie `Lists`) : chaque section décrit une espèce ou un plat différent. Un lien vers
  une de ces sections est une Mention de l'entrée, nommée par la section, qui est aussi le titre de
  la redirection du wiki : `[[Animal Species/Arabasta Saga#Bananawani|Bananawani]]` et
  `[[Bananawani]]` sont la même Entity, typée par les catégories du catalogue (Object). Le catalogue
  lui-même (`[[Animal Species|Animals]]`) n'est pas une Entity, comme un Concept. Les entrées d'un
  catalogue lui-même exclu (`Marine Ranks#Commodore`, un Title) sont exclues aussi.

### Étape 3 : retrouver les noms que le wiki n'a pas liés

**Problème :** le wiki ne lie un nom qu'à sa première apparition sur une page. Au chapitre 1000,
« Luffy » est lié une fois, puis écrit en texte simple une douzaine de fois.

**Solution (Alias match) :** dans chaque Scene, on cherche les Canonical names et les Aliases déjà
datés des Entities **liées quelque part dans le même chapitre**. Règles de sécurité :

- **Sensible à la casse :** « Queen » (le personnage) est retrouvé, « queen » (le mot) ne l'est pas.
- **Seulement les Entities liées dans ce chapitre :** on ne cherche pas « Queen » dans un chapitre
  où le personnage Queen n'est jamais lié. Cela évite la plupart des fausses correspondances.
- **Le nom le plus long d'abord**, et un nom partagé par deux Entities liées dans le même chapitre
  est ignoré.

Résultat : deux tiers des Mentions (45 602 sur 67 923) viennent de cette étape.

### Étape 4 : le Cast depuis la table des personnages

Chaque page de chapitre a une table des personnages qui liste qui apparaît, en indiquant s'il est
présent, en flashback (*Recall*) ou seulement en page de couverture (*Cover appearance*). Chaque
personnage listé entre dans Registry(t) à ce chapitre, **même si le résumé ne le nomme jamais**. Un
en-tête de faction lié (`;[[Straw Hat Pirates]]`) ajoute le Group à Registry(t) sans compter comme
une Mention.

### Étape 5 : un type par Entity

Chaque Entity reçoit **exactement un type pour toute l'histoire**, décidé dans cet ordre :

1. **Les corrections manuelles** (`reference/type_overrides.csv`, 6 entrées) l'emportent sur tout.
   Elles tranchent les cas limites selon le rôle principal de l'Entity dans l'histoire : Wano Country
   est un Place (pas un régime), Zunesha est un Character (et Zou, sur son dos, un Place distinct).
2. **Les datasets locaux** (`reference/characters.json`, `islands.json`, `devil_fruits.json`), après
   nettoyage des noms : `Edward Newgate [Whitebeard]` → Edward Newgate, `Scien [Queen]` → Queen, le
   nom anglais d'un fruit du démon → son nom japonais.
3. **Les catégories du wiki**, lues sur la page du wiki et converties par des règles ordonnées :
   `Pirate Crews` → Group, `Ships` → Ship, `Swords` → Weapon, `Locations` → Place... L'ordre compte :
   Devil Fruit est testé avant Character, pour que *Gomu Gomu no Mi* ne soit pas typé comme une
   personne. Les catégories sont récupérées une seule fois et enregistrées dans
   `reference/wiki_categories.json` : les exécutions suivantes ne font aucun appel réseau et donnent
   toujours le même résultat.
4. Sinon : **Unknown**.

On ne prend dans les datasets que les noms et les types. Leurs autres champs (affiliation, prime,
vivant/mort, relations) décrivent l'histoire à son dernier chapitre : les utiliser ferait fuiter le
futur.

### Étape 6 : les Titles et les Concepts sont retirés

« Admiral », « Pirate » ou « Haki » sont très souvent liés mais ne sont pas des Entities. Ils sont
retirés :

- par catégorie du wiki : une page dans `Positions` ou `Occupations` est un Title (Rear Admiral,
  Shogun, Cook) ; une page dans `Terms` est un Concept (Jolly Roger, Epithet), sauf si une autre
  catégorie en fait un Group ;
- par la liste écrite à la main `reference/concepts.txt`, pour les cas que les catégories ne
  couvrent pas.

Les redirections du wiki listées dans `reference/redirects.csv` sont fusionnées avec leur cible :
« Eleven Supernovas » devient un Alias de *Worst Generation* au lieu d'une deuxième Entity.

### Étape 7 : les Disguises

Le wiki écrit `[[Denjiro|Kyoshiro]]` dès la toute première apparition de Kyoshiro, alors que le
lecteur n'apprend que bien plus tard que Kyoshiro est Denjiro. Prendre les liens au pied de la
lettre ferait fuiter ce secret.

- L'extraction liste des **candidats Disguise** : des Aliases de personnages qui n'ont aucun mot en
  commun avec leur Canonical name (Kyoshiro → Denjiro, Miss All Sunday → Nico Robin), triés par
  nombre de liens, dans `data/gold/entities/disguise_candidates.csv`.
- Un Disguise fusionne deux Entities que le lecteur connaît déjà. `named_apart_from` est le premier
  chapitre où le Long Summary ou la CharTable nomme le personnage sous son propre nom sans l'Alias,
  avant `named_together_from`, le premier chapitre qui lie les deux (souvent la Revelation). Si
  `named_apart_from` est vide, le vrai nom n'arrive qu'avec l'Alias : c'est une révélation de nom
  (Miss All Sunday → Nico Robin), pas un Disguise.
- Un humain confirme les vrais et note le chapitre de **Revelation** dans `reference/disguises.csv`.
- Avant sa Revelation, un Disguise confirmé est une Entity à part, avec ses propres Mentions. À
  partir de la Revelation, il est fusionné avec le vrai personnage et devient l'un de ses Aliases.

### À quoi ressemble la sortie

`data/gold/entities/registry.jsonl` contient une ligne par Entity et par changement, valable de `valid_from`
à `valid_to` (`null` = toujours valable). `catalog` donne la page catalogue dont l'Entity est une
entrée (`"Animal Species"` pour Bananawani), `null` pour toutes les autres ; comme le type, il ne
change jamais :

```json
{"canonical_name": "Anjo", "entity_type": "Character", "catalog": null, "aliases": [],
 "valid_from": 1, "valid_to": null, "first_chapter_seen": 1,
 "last_chapter_seen": 1, "mention_count": 0}
```

`data/gold/entities/registry_quality.json` contient les mesures de qualité utilisées au §6 et des listes à
relire à la main (les Aliases les plus suspects, les 50 Entities les plus mentionnées avec leur
type, les Entities restées Unknown, les noms exclus par catégorie).

---

## 6. Résultats

Exécution sur le corpus complet, 10 novembre 2026, commit `7b88730`.

| Mesure | Valeur | Objectif | État |
|---|---|---|---|
| Chapitres avec au moins une Scene | 1193 / 1193 (5 776 Scenes) | tous | ✅ |
| Entities distinctes | 2 534 | | |
| Lignes de Registry | 40 792 | | |
| Mentions | 67 923 (33 % liens, 67 % recherche de noms) | | |
| Proxy de précision | 97,8 % | ≥ 80 % | ✅ |
| Proxy de rappel | 53,9 % | ≥ 95 % | ❌, voir §6.1 |
| Mentions typées Unknown | 1,35 % | le plus bas possible | ✅ |
| Noms exclus comme Title/Concept par catégorie | 73 | | |
| Tests | 116 verts, hors ligne | tous verts | ✅ |

**Entities par type :**

| Character | Place | Group | Devil Fruit | Object | Weapon | Ship | Unknown |
|---|---|---|---|---|---|---|---|
| 1 587 | 264 | 159 | 142 | 92 | 61 | 47 | 182 |

**Comment la part d'Unknown a baissé :**

| Étape | Mentions typées Unknown | Entities |
|---|---|---|
| Datasets locaux seuls (ENT-05) | 17,2 % | |
| + catégories du wiki et corrections manuelles (ENT-06) | 1,64 % | 2 623 |
| + Titles exclus par catégorie (#105) | 1,46 % | 2 576 |
| + termes génériques exclus, redirections fusionnées (`7b88730`) | 1,35 % | 2 534 |
| + sous-pages et entrées de catalogue résolues (#106) | 1,33 % | 2 598 |

Les 50 Entities les plus mentionnées et leurs types ont toutes été vérifiées à la main : toutes
correctes.

### 6.1 Pourquoi le proxy de rappel est bas

**Ce qu'il mesure :** parmi les personnages que la table des personnages indique comme présents dans
un chapitre, la part qui a aussi une Mention dans le Long Summary de ce chapitre.

**Ce qu'on a trouvé** (mesure rapide, 10 novembre 2026, sur les 22 434 Appearances à l'image) :

| Cas | Part des Appearances |
|---|---|
| Lié dans le résumé | 53 % |
| Pas lié, mais le nom complet est dans le texte | 4 % |
| Pas lié, mais une partie du nom est dans le texte | 4 % |
| **Le nom n'apparaît nulle part dans le résumé** | **39 %** |

**Dans environ 39 % des cas, le résumé ne nomme tout simplement jamais le personnage.** Les tables de
personnages listent tous ceux qui sont dessinés dans le chapitre, y compris à l'arrière-plan, alors
que le résumé raconte l'histoire en quelques paragraphes. Aucun extracteur qui ne lit que le résumé
ne peut dépasser environ 61 %.

Deux conséquences :

- **L'objectif de 95 % a été fixé sur la mauvaise référence.** Le proxy de rappel mesure surtout la
  complétude des résumés du wiki, pas la qualité de l'extracteur. La vraie marge de progrès, ce sont
  les 4 à 8 % de noms présents dans le texte mais non retrouvés : la recherche de noms ne vise que
  les Entities liées dans le même chapitre (une règle de sécurité voulue, §5 étape 3).
- **Registry(t) ne rate pas ces personnages.** Ils y entrent quand même par la table des personnages
  (étape 4). Ce qui leur manque, c'est une Mention, c'est-à-dire une place dans une Scene précise.

Les pires arcs sont ceux avec de grandes batailles et des foules : Marineford (27 %), Amazon Lily
(33 %), Post-War (35 %). Les meilleurs sont des arcs du début avec peu de personnages : Syrup
Village (78 %), Thriller Bark (76 %).

**Décision à prendre :** redéfinir l'objectif (par exemple, ne mesurer le rappel que sur les
personnages dont le nom apparaît dans le résumé), ou garder la mesure actuelle et l'accepter comme
une description de la source. C'est une décision d'équipe sur l'exigence de qualité (REQ-12), pas
une modification de code.

### 6.2 Précision : les noms retrouvés sont les bons

97,8 % des noms de personnages retrouvés tombent sur un personnage présent dans le Cast du chapitre.
Les Aliases « suspects » en tête de liste sont surtout des personnages dont on **parle** sans qu'ils
soient présents : « Big Mom » (66 correspondances sur 613 hors Cast), « Kaidou » (58 sur 525),
« Whitebeard », « Roger ». Ce sont des Mentions correctes, pas des erreurs.

### 6.3 Sous-pages et catalogues (#106)

Exécution sur tout le corpus, 12 novembre 2026, comparée aux mêmes fichiers de référence avant le
changement.

| Mesure | Avant | Après |
|---|---|---|
| Mentions de *Vegapunk* | 578 | 442 |
| Satellites de Vegapunk dans Registry(t) | 0 | 6 Characters (Shaka 84, Lilith 81, York 55, Atlas 50, Edison 41, Pythagoras 26 Mentions) |
| Autres sous-pages à part | 0 | 11 Weapons (Clima-Tacts, Battle Frankies, Kabuto et Pachinko d'Usopp) |
| `Animal Species`, `Plant and Fungi Species`, `Foods` comme Entities | 40, 4 et 24 Mentions | absents |
| Entrées de catalogue | 0 | 62 (44 animaux, 14 aliments, 3 plantes, 1 technologie) |
| Entities distinctes | 2 535 | 2 598 |

Catalogues trouvés : *Animal Species*, *Plant and Fungi Species*, *Foods* et *Technology*. *Marine
Base* est aussi un catalogue, mais son seul lien de section pointe vers un intertitre de liste : il
n'ajoute aucune entrée.

---

## 7. Les problèmes rencontrés, et ce qu'on a fait

| Problème | Exemple | Ce qu'on a fait |
|---|---|---|
| Un outil de NLP généraliste ne connaît pas les noms de One Piece | Zoro classé comme lieu | Arrêter de deviner : utiliser les liens du wiki, déjà résolus par les contributeurs |
| Regrouper les noms par ressemblance fusionne des choses sans rapport | *Ohara* fusionné avec 45 noms | Idem : l'identité est le titre de la page du wiki, pas de clustering |
| Le wiki ne lie un nom qu'une fois par page | « Luffy » lié une fois au ch. 1000 | Alias match, limité aux Entities liées dans le même chapitre, sensible à la casse |
| Le texte d'un lien n'est pas toujours un nom | `[[Marshall D. Teach\|man]]` | Majuscule + liste de mots courants ; le lien compte quand même comme Mention |
| Le wiki révèle les identités secrètes dès le début | `[[Denjiro\|Kyoshiro]]` | Candidats Disguise, confirmation humaine, chapitre de Revelation |
| Les datasets ne couvrent que personnages, îles et fruits du démon | équipages, navires, sabres tous Unknown (17,2 %) | Catégories du wiki avec règles ordonnées, en cache local |
| Les noms des datasets ne correspondent pas toujours aux titres du wiki | `Cutty Flam [Franky]` contre `Franky` | Nettoyage des noms ; l'épithète entre crochets sert de nom |
| Certaines Entities relèvent de deux types | Wano Country : lieu et régime | Un type selon le rôle principal dans l'histoire ; fichier de corrections manuelles |
| Des rangs et des mots généraux devenaient des Entities | Rear Admiral, Cook, Jolly Roger | Exclus par catégorie du wiki (`Positions`, `Occupations`, `Terms`) + `concepts.txt` |
| Les classes d'armes génériques partagent leurs catégories avec les armes nommées | Katana, Firearm | Ajoutées à la main dans `concepts.txt` |
| Deux titres du wiki pour une même chose | Eleven Supernovas / Worst Generation | `redirects.csv` : la redirection devient un Alias |
| Une sous-page déplacée sur le wiki garde son ancien titre en redirection | `Usopp's Arsenal/Kabuto` et `Usopp Tactics/Kabuto`, la même arme | Anciens titres ajoutés à `redirects.csv` |
| Des choses distinctes vivent sur des sous-pages | les six satellites fusionnés dans Vegapunk (578 Mentions), York absent | Une sous-page dont les catégories donnent un type est une Entity à part, nommée par son titre complet |
| Les pages de liste avalent leurs entrées | une fausse Entity `Animal Species` (40 Mentions) ; Bananawani perdu | Une section d'une page `Lists` est une entrée nommée par la section ; la page de liste est écartée |
| Une page de liste et une redirection vers une de ses entrées ont les mêmes catégories | `News Coo` est dans `Lists` comme `Animal Species` | Une page n'est un catalogue que si le corpus lie une de ses sections ou sous-pages |
| Une section de catalogue peut porter le titre d'une autre page | `Animal Species/Arabasta Saga#Arabasta` (un intertitre) fusionné avec le royaume ; `Foods#Candy` avec le Character Candy | Une section titrée comme une page à part (pas une redirection vers le catalogue) ne désigne rien : le lien est écarté |
| Les champs des datasets décrivent la fin de l'histoire | prime, affiliation, vivant/mort | Jamais lus : seuls les noms et types sont utilisés |
| Les tests ne trouvaient pas le code sans installation | `ModuleNotFoundError` | `pythonpath = ["src"]` dans la config pytest |

---

## 8. Les décisions, et pourquoi

| Décision | Pourquoi | Ce qu'on a écarté |
|---|---|---|
| **Utiliser uniquement le wiki anglais** ([ADR 0001](adr/0001-source-wiki-fandom-anglais.md)) | Complet sur tous les chapitres, rempli environ 70 minutes après la sortie, format stable | Wiki français (plus mis à jour), sources japonaises (aucune structure) |
| **Le titre de la page du wiki est l'identité** | Les contributeurs ont déjà résolu qui est qui ; ni devinette, ni modèle | spaCy + clustering (§4), annotation par LLM (ne passe pas à l'échelle en gratuit) |
| **Seulement ce que le lecteur sait au chapitre t** ([ADR 0002](adr/0002-reader-knowledge-only.md)) | Une information du futur gonflerait les scores de test et échouerait en production | Utiliser les fiches complètes des datasets |
| **Aliases datés par leur première utilisation** | « Lucy » ne doit pas être Sabo avant que le lecteur le sache | Listes d'Aliases non datées |
| **Recherche de noms limitée aux Entities liées dans le même chapitre** | Garde une précision haute (97,8 %) | Chercher tous les noms connus partout : beaucoup de fausses correspondances (« Queen », « Roger ») |
| **Un type fixe par Entity** | Une entrée simple et stable pour le modèle | Des types qui changent dans le temps |
| **Ordre de priorité fixe : correction > dataset > catégorie wiki > Unknown** | Prévisible ; un humain peut toujours avoir le dernier mot | Vote ou score entre les sources |
| **Les Titles et Concepts ne sont jamais des Entities** | « Admiral » est porté par plusieurs personnes au fil du temps ; c'est un attribut | Traiter les rangs comme des Groups |
| **Noms limites exclus volontairement** (Royal Guards, Mountain Bandits, New Age, Pantri) | Leur page wiki décrit un rôle ou une idée, pas un groupe précis ; une correction manuelle peut les rétablir | Les garder comme Entities Unknown |
| **Une sous-page à part garde son titre complet** (`Vegapunk/Lilith`) | C'est le titre de la page du wiki, donc l'identité reste unique ; le nom court en est l'Alias | Les noms courts (« Lilith »), qui peuvent entrer en collision avec d'autres pages |
| **Une entrée de catalogue est nommée par sa section** (`Bananawani`) | Même nom que la redirection du wiki : un lien direct et un lien de section donnent une seule Entity | L'ancre complète (`Animal Species/Arabasta Saga#Bananawani`) |
| **Catalogues trouvés par la catégorie `Lists` du wiki, pas à la main** | Aucune liste à tenir ; `Dials` attend (voir §9) | Une liste de catalogues écrite à la main |
| **Catégories du wiki en cache dans le dépôt** | Même résultat à chaque exécution, fonctionne hors ligne, reproductible par quelqu'un d'autre | Interroger le wiki à chaque exécution |
| **Disguises confirmés par un humain** | La détection automatique propose, une personne décide ; un faux Disguise couperait un personnage en deux | Détection entièrement automatique |
| **Disguises pour les Characters seulement (v1)** | L'essentiel de la valeur pour le moins d'effort ; la fuite pour les autres types est acceptée | Tous les Entity types |
| **Une fonction pure, toutes les entrées/sorties à l'extérieur** | Tests rapides hors ligne sur de vrais extraits du wiki ; facile à raisonner | Extraction mêlée aux accès fichiers et réseau |
| **Le texte actuel du wiki sert pour les 1193 chapitres passés** | C'est la seule version disponible ; des éditions ultérieures peuvent contenir des formulations rétrospectives, limite acceptée et documentée | Reconstruire la première révision de chaque page |

---

## 9. Limites connues et suites

1. **Objectif de rappel (§6.1).** Décider comment REQ-12 doit mesurer le rappel. En option, essayer
   de rechercher aussi les noms des personnages du Cast du chapitre même s'ils ne sont pas liés dans
   le résumé, et mesurer si la précision tient.
2. **La relecture des Disguises n'est pas faite.** `reference/disguises.csv` est encore vide, donc
   **le Registry(t) actuel laisse encore fuiter les identités secrètes** (Kyoshiro est compté comme
   Denjiro dès sa première apparition). 197 candidats attendent dans
   `data/gold/entities/disguise_candidates.csv` ; les 72 sans `named_apart_from` sont des révélations
   de nom et peuvent être rejetés. Beaucoup d'autres sont de simples surnoms (« Big Mom » → Charlotte
   Linlin, « Kizaru » → Borsalino) et doivent être rejetés aussi ; les vrais (Kyoshiro, Komurasaki,
   Kamazo...) attendent leur chapitre de Revelation.
3. **182 Entities restent Unknown** (1,35 % des Mentions). La plupart sont des notions laissées
   volontairement sans type : peuples et tribus (Shandia, Mink Tribe), styles de combat (Three Sword
   Style), événements (Buster Call, Levely). Il faut décider s'il leur faut un type ou s'il faut les
   exclure comme des Concepts.
4. **Formulations rétrospectives dans les anciens résumés.** Les textes des chapitres passés sont la
   version actuelle du wiki et peuvent contenir des formulations écrites après des révélations
   ultérieures (ADR 0002, limite acceptée).
5. **Les noms issus des datasets ne sont jamais vérifiés par les catégories du wiki.** Un Title
   présent dans un dataset ne serait pas exclu. Une vérification manuelle n'en a trouvé aucun.
6. **`Dials` reste fusionné.** Sa page est construite comme un catalogue (Impact Dial, Reject Dial,
   Jet Dial sont des sections, 40 Mentions) mais n'est pas dans la catégorie `Lists` : ses entrées
   comptent toujours comme des Mentions de `Dials`. Le corriger demande une liste de catalogues
   écrite à la main, volontairement hors du ticket #106.
7. **Les entrées de catalogue valent ce que valent les titres de section du wiki.** Quelques-unes
   sont des intertitres ou des variantes : `Other Varieties 2` (Foods), `Kung Fu Dugongs` à côté de
   `Kung-Fu Dugongs`. Les redirections jamais liées par une section (`Weather Ball`, `Mizu Mizu
   Meat`) restent des Entities mais ont `catalog: null`.

---

## 10. Comment relancer

```bash
python -m guess_arc.entities            # tout le corpus ; ne récupère que les catégories absentes du cache
python -m guess_arc.entities --offline  # aucun accès réseau
pytest                                  # 127 tests, hors ligne
```

| Fichier | Rôle | Modifié par |
|---|---|---|
| `src/guess_arc/entities/extraction.py` | Toutes les règles (fonction pure) | code |
| `src/guess_arc/entities/pipeline.py` | Lit le bronze, récupère les catégories, écrit le gold | code |
| `reference/type_overrides.csv` | Types fixés à la main | humain |
| `reference/concepts.txt` | Titles et Concepts exclus à la main | humain |
| `reference/redirects.csv` | Redirections du wiki fusionnées avec leur cible | humain |
| `reference/disguises.csv` | Disguises confirmés et leur chapitre de Revelation | humain |
| `reference/wiki_categories.json` | Cache des catégories du wiki | pipeline |
| `data/gold/entities/registry.jsonl` | Registry(t) | pipeline |
| `data/gold/entities/registry_quality.json` | Rapport de qualité | pipeline |
| `data/gold/entities/disguise_candidates.csv` | Candidats Disguise à relire | pipeline |

Plus de détails : [README](../README.md#entity-extraction), vocabulaire dans
[CONTEXT.md](../CONTEXT.md).
