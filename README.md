# GUESS.ARC

[![tests](https://github.com/EPF-MDE/GUESS.ARC/actions/workflows/tests.yml/badge.svg)](https://github.com/EPF-MDE/GUESS.ARC/actions/workflows/tests.yml)

Predict the content of *One Piece* chapter n+1 from chapters 1 to n.

The repository currently holds the data pipeline up to the **silver** layer.
Modelling (a sequential, GRU-based architecture) will plug into it in a later
step. The earlier simple-taxonomy approach has been dropped.

## Layout

```
src/guess_arc/
├── paths.py              # locations of data/bronze, data/silver, data/state.json
└── ingestion/            # English Fandom wiki -> bronze -> silver
    ├── wiki_client.py    # MediaWiki API calls
    ├── parser.py         # a chapter's wikitext -> Chapter
    ├── silver.py         # Chapter -> data/silver/chapter_NNNN.md
    ├── validation.py     # bronze / silver format contract
    └── pipeline.py       # orchestration, incremental state, CLI
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
- a check of every file in `data/bronze/` and `data/silver/`
  (skipped if the data hasn't been generated yet).

## Data source

English One Piece wiki only. French and Japanese sources are ruled out, see
[ADR 0001](docs/adr/0001-source-wiki-fandom-anglais.md).

Fandom wiki content is licensed under CC BY-SA: academic use with attribution.
The client sends a `User-Agent` identifying the project and rate-limits its
requests.
