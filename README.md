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
    ├── future_leaks.py   # passages qui parlent de la suite, retirés après relecture
    ├── inputs.py         # data/event/in/events_NNNN.md : le prompt utilisateur exact
    ├── versions.py       # versions du prompt et des entités
    └── pipeline.py       # orchestration, CLI
tests/                    # tests sans réseau
docs/adr/                 # décisions d'architecture
review/future_leaks.json  # relecture humaine des fuites du futur (versionnée)
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

### Fuites du futur

Le préparsing repère par expression régulière les passages qui parlent de la
suite de l'histoire (« would later », « in the future », « foreshadowing »…) :
une phrase des résumés, ou une note entière. Il les liste dans
`data/event/future_leak_candidates.json` (chapitre, section, passage, décision),
mais ne les retire du texte qu'une fois relus :

1. lancer `python -m guess_arc.events --dry-run` ; la sortie indique combien de
   candidats restent à relire ;
2. dans `review/future_leaks.json` (versionné), mettre `decision` à `"remove"`
   pour un passage qui révèle la suite, à `"keep"` sinon (ellipse du récit,
   « Brook is later seen… » à l'intérieur du chapitre). Un nouveau candidat se
   copie depuis la liste des candidats ;
3. relancer : les passages `remove` disparaissent de `in/` et sont comptés dans
   `flags.future_leaks_removed`. Un passage `keep` ou pas encore relu (`null`)
   reste dans le texte.

Un passage est reconnu à son texte exact : si la silver change, il redevient un
candidat à relire.

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
  chapitres silver synthétiques dans un dossier de données temporaire, dont la
  détection et le retrait des fuites du futur selon le fichier de relecture ;
- le contrôle de tous les fichiers de `data/bronze/` et `data/silver/`
  (ignoré si les données n'ont pas encore été générées).

## Source de données

Wiki One Piece anglais uniquement. Les sources françaises et japonaises sont
écartées, voir [ADR 0001](docs/adr/0001-source-wiki-fandom-anglais.md).

Le contenu du wiki Fandom est sous licence CC BY-SA : usage académique avec
attribution. Le client envoie un `User-Agent` identifiant le projet et limite
son débit.
