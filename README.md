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
└── events/               # Event type discovery and Event extraction (in progress)
    └── llm.py            # pluggable LLM backend: config, schema validation, response cache
configs/
└── events.json           # LLM model of each Event task (no secrets)
reference/                # versioned reference data
├── characters.json, islands.json, devil_fruits.json   # datasets (Entity types)
├── concepts.txt          # Concepts and Titles, excluded from Registry(t)
├── wiki_categories.json  # cache of the wiki's categories (Entity types)
├── type_overrides.csv    # Entity types set by hand
├── redirects.csv         # wiki redirects merged into their target's Canonical name
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
a Mention of the Entity whose Canonical name is the target page.
A part of a page (`[[Page/Subpage]]`, `[[Page#Section]]`) counts for the parent
page, with two exceptions decided by wiki categories. A subpage whose own
categories give an Entity type is a separate Entity, named by its full title
(`Vegapunk/Lilith`, Character). A page in the `Lists` category that is linked to a
section somewhere in the corpus is a catalog (`Animal Species`, `Foods`): a link to
one of its sections is a Mention of the entry, named by the section
(`[[Animal Species/Arabasta Saga#Bananawani]]` -> Bananawani, like the wiki's
redirect), typed by the catalog's categories; the catalog itself is not an Entity.
A section titled like a page of its own (`#Arabasta`, a heading) is dropped
rather than merged. The entries of an excluded catalog (`Marine Ranks`) are
excluded too.
The text of a piped link (`[[Edward Newgate|Whitebeard]]`) becomes an Alias if it
looks like a name: initial capital, first word not in `common_words.txt`, and the
link names the Entity itself, not a part of a page. Each Alias is dated by the
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
`reference/wiki_categories.json`: only Entities still Unknown, linked subpages,
parents of section or subpage links and catalog entries missing from the
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
Plain-language account of the step, its results, problems and decisions:
[docs/entity-extraction.md](docs/entity-extraction.md) (French: [docs/entity-extraction.fr.md](docs/entity-extraction.fr.md)).

- `data/gold/entities/registry.jsonl`: Registry(t), one line per Entity and per change,
  valid from `valid_from` to `valid_to` inclusive (`null`: still valid), with the
  Entity type, the catalog it is an entry of (`"Animal Species"` for Bananawani,
  `null` otherwise), the Aliases used so far, the first and last chapter seen and
  the number of Mentions up to t
- `data/gold/entities/registry_quality.json`: quality report (Scenes per chapter; recall
  proxy, overall and per arc: share of Characters with an Appearance in the
  CharTable that have at least one Mention in the chapter's Long Summary; Mentions
  by source, link or Alias match; precision proxy: share of Character Alias matches
  that fall within the chapter's Cast; the 20 most suspicious Aliases, those that
  most often fall outside the Cast; share of Mentions typed Unknown; the 50 most
  mentioned Entities with their type)
- `data/gold/entities/disguise_candidates.csv`: possible Disguises, sorted by number of
  links. A candidate is a Character Alias that shares no word with its Canonical
  name (`Kyoshiro` -> Denjiro), found in the Long Summary, the CharTable and the
  Chapter Notes. Regenerated on every run: real Disguises are confirmed by hand,
  with their Revelation chapter, then copied into `reference/disguises.csv`.

## LLM backend (Events)

Event type discovery and Event extraction call an LLM through one shared backend
(`src/guess_arc/events/llm.py`). Each call sends a prompt and a JSON schema and gets
back structured output that is checked against the schema: an answer that is not
JSON, does not match the schema, or stopped early (refusal, `max_tokens`) raises
`StructuredOutputError`. It is never accepted as is, and never cached.

**Choosing the model.** The model of each task is set in `configs/events.json`, as
`provider:model-name`:

```json
{
  "discovery_model": "anthropic:claude-opus-5-5",
  "extraction_model": "anthropic:claude-opus-5-5"
}
```

Switching model means editing this file, nothing else. Known providers: `anthropic`.
Adding one (another API, a local model) means writing one adapter class with a
`model` attribute and a `complete(prompt, schema) -> str` method, and adding it to
`PROVIDERS` in `llm.py`; callers don't change. The default models are a placeholder:
the team picks them by comparing candidates on the validation sample (#114).

**API keys** come from the environment, never from a committed file. For Anthropic,
set `ANTHROPIC_API_KEY` in the shell that runs the pipeline:

| OS / shell | Command |
|---|---|
| macOS / Linux, Git Bash | `export ANTHROPIC_API_KEY=sk-ant-...` |
| Windows, PowerShell | `$env:ANTHROPIC_API_KEY = "sk-ant-..."` |
| Windows, cmd | `set ANTHROPIC_API_KEY=sk-ant-...` |

If you keep the key in a `.env` file, it is git-ignored; the code does not read it
itself, so load it into the environment first.

**Temperature.** Adapters send temperature 0 when their API accepts it. The
Anthropic API no longer does: since API version `2026-10-21`, any `temperature`,
`top_p` or `top_k` is rejected (HTTP 400) on every model, so the Anthropic adapter
sends none. Reproducibility comes from the cache below. Server-side fallback to
another model is off, so an answer always comes from the model named in the cache key.

**Response cache.** Every validated answer is stored under `data/bronze/llm/`, like
the raw wikitext (an external source we archive), one file per key
(model, prompt version, taxonomy version, chapter):

```
data/bronze/llm/<provider>/<model-name>/<prompt_version>/<taxonomy_version>/chapter_NNNN.json
```

A second run with the same key makes no network call. Changing any of the four
parts (another model, a new prompt version, a new taxonomy version) makes a fresh
call; the old answers stay on disk. The prompt text itself is not part of the key:
**bump the prompt version whenever you change a prompt or schema**, otherwise the
old answers are served. Delete a folder to force new calls.

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
- the LLM backend, with a fake backend that counts its calls and a fake Anthropic
  SDK client (no network): schema validation, the response cache and its
  four-part key, the model chosen from the config, the request sent to Claude;
- a check of every file in `data/bronze/` and `data/silver/`
  (skipped if the data hasn't been generated yet).

## Data source

English One Piece wiki only. French and Japanese sources are ruled out, see
[ADR 0001](docs/adr/0001-source-wiki-fandom-anglais.md).

Fandom wiki content is licensed under CC BY-SA: academic use with attribution.
The client sends a `User-Agent` identifying the project and rate-limits its
requests.
