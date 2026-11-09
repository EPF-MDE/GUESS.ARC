# GUESS.ARC

[![tests](https://github.com/EPF-MDE/GUESS.ARC/actions/workflows/tests.yml/badge.svg)](https://github.com/EPF-MDE/GUESS.ARC/actions/workflows/tests.yml)

Predict the content of *One Piece* chapter n+1 from chapters 1 to n.

The repository currently holds the data pipeline up to the **silver** layer,
plus entity extraction into the **gold** layer (Registry(t)).
Modelling (a sequential, GRU-based architecture) will plug into it in a later
step. The earlier simple-taxonomy approach has been dropped.

## Layout

```
src/guess_arc/
├── paths.py              # locations of data/bronze, data/silver, data/gold, data/state.json
├── ingestion/            # English Fandom wiki -> bronze -> silver
│   ├── wiki_client.py    # MediaWiki API calls
│   ├── parser.py         # a chapter's wikitext -> Chapter
│   ├── silver.py         # Chapter -> data/silver/chapter_NNNN.md
│   ├── validation.py     # bronze / silver format contract
│   └── pipeline.py       # orchestration, incremental state, CLI
└── entities/             # bronze -> Scenes -> Mentions -> Registry(t) in gold
    ├── extraction.py     # extract_entities(chapters, reference): pure, single entry point
    ├── pipeline.py       # reads bronze, writes gold, CLI
    └── common_words.txt  # common words: link text starting with one of them is not an Alias
reference/                # versioned reference data
├── characters.json, islands.json, devil_fruits.json   # datasets (Entity types)
├── concepts.txt          # Concepts and Titles, excluded from Registry(t)
├── wiki_categories.json  # cache of the wiki's categories (Entity types)
├── type_overrides.csv    # Entity types set by hand
└── disguises.csv         # Disguises confirmed by hand, with their Revelation
scripts/quality/          # corpus quality checks (see QUALITY.md)
tests/                    # network-free tests
docs/adr/                 # architecture decision records
QUALITY.md                # quality requirements, evidence and client validation
```

Future stages (features, model) will be added as sub-packages of `guess_arc`,
next to `ingestion`. They will read the silver layer through `guess_arc.paths`.

## Setup

Requirements: **Python 3.10 or later**, Git, and an internet connection for the
ingestion step (tests and quality checks run offline). Works on Windows, macOS
and Linux.

```bash
git clone https://github.com/EPF-MDE/GUESS.ARC.git
cd GUESS.ARC
```

Create and activate a virtual environment. On macOS / Linux, `python` often
doesn't exist or points to Python 2: use `python3` for this one command.

| OS / shell | Create | Activate |
|---|---|---|
| macOS / Linux | `python3 -m venv .venv` | `source .venv/bin/activate` |
| Windows, cmd | `python -m venv .venv` | `.venv\Scripts\activate` |
| Windows, PowerShell | `python -m venv .venv` | `.venv\Scripts\Activate.ps1` |
| Windows, Git Bash | `python -m venv .venv` | `source .venv/Scripts/activate` |

If PowerShell refuses to run `Activate.ps1` ("running scripts is disabled on this
system"), allow local scripts once for your user, then activate again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Once the environment is active, `python` and `pip` point to it on every OS:

```bash
python --version                  # check: 3.10 or later
pip install -r requirements.txt   # installs guess_arc in editable mode + pytest
```

All the commands below assume the environment is active.

## Ingestion

Needs internet access (English One Piece Fandom wiki API, no account or API key).

```bash
# full run: every chapter, ~24 requests, under a minute
python -m guess_arc.ingestion --max-chapter 1193

# weekly update: only reprocesses pages whose revision has changed
python -m guess_arc.ingestion --max-chapter 1200 --incremental

# after a parser change: rebuild silver from bronze, no network
python -m guess_arc.ingestion --rebuild-silver
```

Outputs always go under `data/` at the repo root (override with `--data-dir`):

- `data/bronze/chapters.jsonl`: the archived raw wikitext, one line per chapter
- `data/silver/chapter_NNNN.md`: one file per chapter, a YAML front-matter (title,
  arc, characters with their faction and `on_panel`) followed by the short summary,
  the long summary and the notes
- `data/state.json`: the known `revid`s, for incremental runs

## Entity extraction

```bash
# all of bronze -> Registry(t), no network needed except for uncached wiki categories
python -m guess_arc.entities
```

Each paragraph of the Long Summary is a Scene; each `[[...]]` link in a Scene is
a Mention of the Entity whose Canonical name is the target page
(`[[Page/Subpage]]` and `[[Page#Section]]` count for the parent page).
The text of a piped link (`[[Edward Newgate|Whitebeard]]`) becomes an Alias if it
looks like a name: initial capital, first word not in `common_words.txt`, and the
link points neither to a subpage nor to a section. Each Alias is dated by the
chapter of its first use.
Since the wiki only links an Entity at its first occurrence in a page, its
unlinked occurrences are recovered by Alias match: in each Scene, we search
(case-sensitive) for the Canonical name and the already-dated Aliases of the
Entities linked in the same chapter.
The Cast comes from the CharTable: a Character with an Appearance, a Recall or a
Cover appearance enters Registry(t) at that chapter, even without a Mention; a
linked faction header (`;[[Straw Hat Pirates]]`) adds its Group, without counting
a Mention.
Each Entity gets exactly one fixed Entity type: Character, Place or Devil Fruit if
its Canonical name is in `reference/characters.json`, `islands.json` or
`devil_fruits.json` (name without the bracketed epithet or the trailing
parenthesis, or a Character's bracketed epithet: `Scien [Queen]` -> Queen; a Devil
Fruit's English name mapped to its Japanese name). Otherwise, the categories of its
wiki page give the type (`Pirate Crews` -> Group, `Ships` -> Ship, `Swords` ->
Weapon, `Locations` -> Place...), following a priority order documented in
`extraction.py`. Failing that, the Entity is Unknown. `reference/type_overrides.csv`
wins over everything else. Categories are cached in
`reference/wiki_categories.json`: only Entities still Unknown and missing from the
cache are requested from the wiki, in batches of 50 (`--offline` to request
nothing). Only the datasets' names are used: their state attributes are never
read. The Concepts and Titles in `reference/concepts.txt` (`Pirate`, `Haki`,
`Admiral`...) are excluded from Registry(t).
The confirmed Disguises in `reference/disguises.csv` (alias, Canonical name,
Revelation chapter) are applied: before the Revelation, the Disguise is an Entity
in its own right (Kyoshiro has his own Mentions, linked or by Alias match, and his
own CharTable presence); from the Revelation on, it merges into its Canonical name,
which takes over its Mentions and gets it as an Alias dated from that chapter.
Empty list: unchanged output.
Vocabulary: [CONTEXT.md](CONTEXT.md). Constraint: [ADR 0002](docs/adr/0002-reader-knowledge-only.md).

- `data/gold/registry.jsonl`: Registry(t), one line per Entity and per change,
  valid from `valid_from` to `valid_to` inclusive (`null`: still valid), with the
  Entity type, the Aliases used so far, the first and last chapter seen and the
  number of Mentions up to t
- `data/gold/registry_quality.json`: quality report (Scenes per chapter; recall
  proxy, overall and per arc: share of Characters with an Appearance in the
  CharTable that have at least one Mention in the chapter's Long Summary; Mentions
  by source, link or Alias match; precision proxy: share of Character Alias matches
  that fall within the chapter's Cast; the 20 most suspicious Aliases, those that
  most often fall outside the Cast; share of Mentions typed Unknown; the 50 most
  mentioned Entities with their type)
- `data/gold/disguise_candidates.csv`: possible Disguises, sorted by number of
  links. A candidate is a Character Alias that shares no word with its Canonical
  name (`Kyoshiro` -> Denjiro), found in the Long Summary, the CharTable and the
  Chapter Notes. Regenerated on every run: real Disguises are confirmed by hand,
  with their Revelation chapter, then copied into `reference/disguises.csv`.

## Quality checks

```bash
python scripts/quality/check_silver.py [--silver PATH] [--expected 1193]
```

Checks that the silver corpus is a sound input for the next stages: no missing
chapters, a valid front-matter in every file, a non-empty long summary, and a
`character_count` that matches the listed characters. Standard library only, no
network; exits with code 1 if anything fails. By default it reads `data/silver/`
at the repo root, whatever the current directory. The requirements it covers
(REQ-5 to REQ-8) and the results are tracked in [QUALITY.md](QUALITY.md).

## Tests

```bash
pytest
```

No network access is needed. GitHub Actions CI (`.github/workflows/tests.yml`)
runs the same command on every PR and every push to `main`, on Ubuntu and Windows,
with Python 3.10 and 3.12. `data/` doesn't exist there, so the checks on the real
corpus are skipped (`pytest -rs` shows why). The tests cover:

- the parser, on real excerpts from chapters 500 and 1193: bare-parenthesis
  annotations in older chapters (`*[[Kalifa]] (cover)`) and quoted ones in
  recent chapters (`*[[King]] ''(cover)''`);
- the bronze and silver format contract, on synthetic fixtures;
- entity extraction through `extract_entities` alone, on real bronze excerpts
  (Scenes, Mentions, dated Aliases, Alias match, CharTable Cast, recall and
  precision proxies, Entity types from the datasets, wiki categories and
  overrides, category cache, confirmed Disguises, Registry(t) over 3 chapters,
  Disguise candidates);
- a check of every file in `data/bronze/` and `data/silver/`
  (skipped if the data hasn't been generated yet).

## Data source

English One Piece wiki only. French and Japanese sources are ruled out, see
[ADR 0001](docs/adr/0001-source-wiki-fandom-anglais.md).

Fandom wiki content is licensed under CC BY-SA: academic use with attribution.
The client sends a `User-Agent` identifying the project and rate-limits its
requests.
