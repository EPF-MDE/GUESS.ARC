# GUESS.ARC

Prédire le contenu du chapitre n+1 de *One Piece* à partir des chapitres 1 à n.

Le dépôt contient aujourd'hui la chaîne de données jusqu'à la couche **silver**.
La modélisation (architecture séquentielle à base de GRU) viendra s'y brancher
dans un second temps. L'ancienne approche par taxonomie simple a été abandonnée.

## Structure

```
src/guess_arc/
├── paths.py              # emplacements data/bronze, data/silver, data/event, data/state.json
├── ingestion/            # wiki Fandom EN -> bronze -> silver
│   ├── wiki_client.py    # appels à l'API MediaWiki
│   ├── parser.py         # wikitexte d'un chapitre -> Chapter
│   ├── silver.py         # Chapter -> data/silver/chapter_NNNN.md
│   ├── validation.py     # contrat de format bronze / silver
│   └── pipeline.py       # orchestration, état incrémental, CLI
└── events/               # silver -> data/event (extraction des événements)
    ├── silver.py         # lecture d'un chapitre de la silver
    ├── preparse.py       # notes éditoriales et de couverture retirées, texte normalisé
    ├── inputs.py         # data/event/in/events_NNNN.md : le prompt utilisateur exact
    ├── versions.py       # versions du prompt et des entités
    └── pipeline.py       # orchestration, CLI
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
- `data/silver/chapter_NNNN.md` : un fichier par chapitre, front-matter YAML (titre, arc, personnages avec faction, `on_panel` et `appearance`, la liste normalisée de leurs annotations parmi `cover`, `flashback`, `mentioned`, `dream`, `ko`, `image`, `other`) puis résumé court, résumé long et notes
- `data/state.json` : les `revid` connus, pour les runs incrémentaux

## Extraction des événements

En cours (spec : issue #88). Seul le préparsing est livré pour l'instant :

```bash
# écrit data/event/in/events_NNNN.md pour chaque chapitre, sans appeler le modèle
python -m guess_arc.events --dry-run

# sur une plage de chapitres
python -m guess_arc.events --dry-run --from 90 --to 100
```

Chaque fichier d'entrée porte un front-matter (`chapter`, `revision_id` de la
silver, `entities_version`, `prompt_version`, `flags` : le décompte des notes
retirées par catégorie), puis le prompt utilisateur exact : numéro, titre, arc,
résumé court, résumé long et notes, sans notes éditoriales (début ou fin d'arc,
anime, volume, SBS) ni notes de couverture, avec un texte normalisé (entités
HTML, espaces insécables, restes de balisage wiki, espaces multiples).

## Tests

```bash
pytest
```

Aucun accès réseau n'est nécessaire. Les tests couvrent :

- le parseur, sur des extraits réels des chapitres 500 et 1193 : annotations
  en parenthèses nues des anciens chapitres (`*[[Kalifa]] (cover)`) et
  en apostrophes des récents (`*[[King]] ''(cover)''`) ;
- le contrat de format bronze et silver, sur des fixtures synthétiques ;
- le préparsing de l'extraction des événements, à travers `--dry-run`, sur des
  chapitres silver synthétiques dans un dossier de données temporaire ;
- le contrôle de tous les fichiers de `data/bronze/` et `data/silver/`
  (ignoré si les données n'ont pas encore été générées).

## Source de données

Wiki One Piece anglais uniquement. Les sources françaises et japonaises sont
écartées, voir [ADR 0001](docs/adr/0001-source-wiki-fandom-anglais.md).

Le contenu du wiki Fandom est sous licence CC BY-SA : usage académique avec
attribution. Le client envoie un `User-Agent` identifiant le projet et limite
son débit.
