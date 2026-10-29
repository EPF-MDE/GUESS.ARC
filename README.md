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
    └── pipeline.py       # lecture du bronze, écriture de la gold, CLI
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
Vocabulaire : [CONTEXT.md](CONTEXT.md). Contrainte : [ADR 0002](docs/adr/0002-reader-knowledge-only.md).

- `data/gold/registry.jsonl` : Registry(t), une ligne par Entity et par changement,
  valable de `valid_from` à `valid_to` inclus (`null` : encore valable), avec
  premier et dernier chapitre vu et nombre de Mentions jusqu'à t
- `data/gold/registry_quality.json` : rapport qualité (Scenes par chapitre)

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
  du bronze (Scenes, Mentions, Registry(t) sur 3 chapitres) ;
- le contrôle de tous les fichiers de `data/bronze/` et `data/silver/`
  (ignoré si les données n'ont pas encore été générées).

## Source de données

Wiki One Piece anglais uniquement. Les sources françaises et japonaises sont
écartées, voir [ADR 0001](docs/adr/0001-source-wiki-fandom-anglais.md).

Le contenu du wiki Fandom est sous licence CC BY-SA : usage académique avec
attribution. Le client envoie un `User-Agent` identifiant le projet et limite
son débit.
