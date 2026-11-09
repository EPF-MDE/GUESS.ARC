# GUESS.ARC

Prédire le contenu du chapitre n+1 de *One Piece* à partir des chapitres 1 à n.

Le dépôt contient aujourd'hui la chaîne de données jusqu'à la couche **silver**.
La modélisation (architecture séquentielle à base de GRU) viendra s'y brancher
dans un second temps. L'ancienne approche par taxonomie simple a été abandonnée.

## Structure

```
src/guess_arc/
├── paths.py              # emplacements data/bronze, data/silver, data/gold, data/state.json
├── ingestion/            # wiki Fandom EN -> bronze -> silver
│   ├── wiki_client.py    # appels à l'API MediaWiki
│   ├── parser.py         # wikitexte d'un chapitre -> Chapter
│   ├── silver.py         # Chapter -> data/silver/chapter_NNNN.md
│   ├── validation.py     # contrat de format bronze / silver
│   └── pipeline.py       # orchestration, état incrémental, CLI
└── entities/             # bronze -> Scenes -> Mentions -> Registry(t) dans la gold
    ├── extraction.py     # extract_entities(chapters, reference), pure, seul point d'entrée
    ├── pipeline.py       # lecture du bronze, écriture de la gold, CLI
    └── common_words.txt  # mots courants : un texte de lien qui commence par l'un d'eux n'est pas un Alias
reference/                # données de référence versionnées
├── characters.json, islands.json, devil_fruits.json   # datasets (Entity types)
├── concepts.txt          # Concepts et Titles, exclus de Registry(t)
├── wiki_categories.json  # cache des catégories du wiki (Entity types)
└── type_overrides.csv    # Entity types fixés à la main
tests/                    # tests sans réseau
docs/adr/                 # décisions d'architecture
```

Les futures étapes (features, modèle) seront ajoutées comme sous-packages de
`guess_arc`, à côté d'`ingestion`. Elles liront la silver via `guess_arc.paths`.

## Environnement

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt   # installe guess_arc en mode éditable + pytest
```

## Ingestion

```bash
# run complet : tous les chapitres, ~24 requêtes, moins d'une minute
python -m guess_arc.ingestion --max-chapter 1194

# mise à jour hebdomadaire : ne retraite que les pages dont la révision a changé
python -m guess_arc.ingestion --max-chapter 1200 --incremental

# après une modification du parseur : régénère la silver depuis le bronze, sans réseau
python -m guess_arc.ingestion --rebuild-silver
```

Sorties, toujours sous `data/` à la racine du repo (modifiable avec `--data-dir`) :

- `data/bronze/chapters.jsonl` : le wikitexte brut archivé, une ligne par chapitre
- `data/silver/chapter_NNNN.md` : un fichier par chapitre, front-matter YAML (titre, arc, personnages avec faction et `on_panel`) puis résumé court, résumé long et notes
- `data/state.json` : les `revid` connus, pour les runs incrémentaux

## Extraction des Entities

```bash
# tout le bronze -> Registry(t), sans réseau
python -m guess_arc.entities
```

Chaque paragraphe du Long Summary est une Scene ; chaque lien `[[...]]` d'une
Scene est une Mention de l'Entity dont le Canonical name est la page cible
(`[[Page/Sous-page]]` et `[[Page#Section]]` comptent pour la page parente).
Le texte d'un lien pipé (`[[Edward Newgate|Whitebeard]]`) devient un Alias s'il
ressemble à un nom : majuscule initiale, premier mot absent de
`common_words.txt`, lien ni vers une sous-page ni vers une section. Chaque Alias
est daté par le chapitre de sa première utilisation.
Le wiki ne liant une Entity qu'à sa première occurrence dans la page, ses
occurrences non liées sont retrouvées par Alias match : dans chaque Scene, on
cherche (sensible à la casse) le Canonical name et les Aliases déjà datés des
Entities liées dans le même chapitre.
Le Cast vient de la CharTable : un Character avec une Appearance, un Recall ou
une Cover appearance entre dans Registry(t) à ce chapitre, même sans Mention ;
un en-tête de faction lié (`;[[Straw Hat Pirates]]`) y ajoute son Group, sans
compter de Mention.
Chaque Entity reçoit un seul Entity type, fixe : Character, Place ou Devil Fruit
si son Canonical name est dans `reference/characters.json`, `islands.json` ou
`devil_fruits.json` (nom sans l'épithète entre crochets ni la parenthèse finale,
ou épithète entre crochets d'un Character : `Scien [Queen]` -> Queen ; nom anglais
d'un Devil Fruit ramené au nom japonais). Sinon, les catégories de sa page sur
le wiki donnent le type (`Pirate Crews` -> Group, `Ships` -> Ship, `Swords` ->
Weapon, `Locations` -> Place...), selon un ordre de priorité documenté dans
`extraction.py`. Faute de mieux, l'Entity est Unknown. `reference/type_overrides.csv`
l'emporte sur tout le reste. Les catégories sont mises en cache dans
`reference/wiki_categories.json` : seules les Entities encore Unknown et absentes
du cache sont demandées au wiki, par lots de 50 (`--offline` pour ne rien demander). Seuls les noms des datasets servent : leurs attributs
d'état ne sont jamais lus. Les Concepts et Titles de `reference/concepts.txt`
(`Pirate`, `Haki`, `Admiral`...) sont exclus de Registry(t).
Vocabulaire : [CONTEXT.md](CONTEXT.md). Contrainte : [ADR 0002](docs/adr/0002-reader-knowledge-only.md).

- `data/gold/registry.jsonl` : Registry(t), une ligne par Entity et par changement,
  valable de `valid_from` à `valid_to` inclus (`null` : encore valable), avec
  Entity type, Aliases déjà utilisés, premier et dernier chapitre vu et nombre
  de Mentions jusqu'à t
- `data/gold/registry_quality.json` : rapport qualité (Scenes par chapitre ;
  recall proxy, global et par arc : part des Characters avec une Appearance dans
  la CharTable qui ont au moins une Mention dans le Long Summary du chapitre ;
  Mentions par source, lien ou Alias match ; precision proxy : part des Alias
  matches de Characters qui tombent dans le Cast du chapitre ; les 20 Aliases
  les plus suspects, ceux qui tombent le plus souvent hors du Cast ; part des
  Mentions typées Unknown ; les 50 Entities les plus mentionnées avec leur type)
- `data/gold/disguise_candidates.csv` : Disguises possibles, triés par nombre de
  liens. Un candidat est un Alias de Character qui ne partage aucun mot avec son
  Canonical name (`Kyoshiro` -> Denjiro), relevé dans le Long Summary, la CharTable
  et les Chapter Notes. Régénéré à chaque run : on y confirme les vrais Disguises
  à la main, avec leur chapitre de Revelation, avant de les recopier ailleurs.

## Tests

```bash
pytest
```

Aucun accès réseau n'est nécessaire. Les tests couvrent :

- le parseur, sur des extraits réels des chapitres 500 et 1193 : annotations
  en parenthèses nues des anciens chapitres (`*[[Kalifa]] (cover)`) et
  en apostrophes des récents (`*[[King]] ''(cover)''`) ;
- le contrat de format bronze et silver, sur des fixtures synthétiques ;
- l'extraction des Entities via `extract_entities` seul, sur des extraits réels
  du bronze (Scenes, Mentions, Aliases datés, Alias match, Cast de la
  CharTable, recall et precision proxies, Entity types des datasets, des catégories du wiki et des overrides, cache des
  catégories, Registry(t) sur 3 chapitres, Disguise candidates) ;
- le contrôle de tous les fichiers de `data/bronze/` et `data/silver/`
  (ignoré si les données n'ont pas encore été générées).

## Source de données

Wiki One Piece anglais uniquement. Les sources françaises et japonaises sont
écartées, voir [ADR 0001](docs/adr/0001-source-wiki-fandom-anglais.md).

Le contenu du wiki Fandom est sous licence CC BY-SA : usage académique avec
attribution. Le client envoie un `User-Agent` identifiant le projet et limite
son débit.
