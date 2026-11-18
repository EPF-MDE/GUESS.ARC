# Quality ledger

The quality requirements agreed with the client (Konrad), how each one is verified, and the
evidence that it was. **Each requirement is a conversation thread** between the team and the
client: an append-only, dated list of entries. The threads are the single source of truth; the
Markdown views are generated from them.

A thread is made of **entries**, never "events": in this repo, an Event is something that happens
in a chapter (see `CONTEXT.md`).

This folder replaces the former `QUALITY.md`: its requirements, verifications, weekly log and
meetings were migrated here (entries flagged `migrated: true`), and it was then removed.

## Where to look

| Grid | What it asks | Where it is shown |
|---|---|---|
| **Q1** | You questioned and specified the quality requirements of your product | [CURRENT.md](CURRENT.md) (spec of every current requirement) and the `proposed` / `revised` / `accepted` / `amended` / `rejected` entries of each thread |
| **Q2** | You defined how you'll know each requirement is met | The *Verification*, *When* and *Owner* of each requirement in [CURRENT.md](CURRENT.md) |
| **Q3** | You actually ran those checks | The `verified` entries (result, evidence, raw output) of each thread; the latest one is in [CURRENT.md](CURRENT.md) |

| File | What it is |
|---|---|
| [CURRENT.md](CURRENT.md) | Generated. What the team must reach now. |
| [OVERVIEW.md](OVERVIEW.md) | Generated. One line per requirement that ever existed, with a link to its thread. |
| `requirements/REQ-<n>.yaml` | One thread per requirement. IDs are never reused. |
| [deliveries.yaml](deliveries.yaml) | One entry per client meeting: date, theme, and a free thread of notes (what was shown, what the client said, decisions, next steps). |
| [data-rules.md](data-rules.md) | Data & confidentiality rules. |

## Sprint rhythm

Sprints last one week; the client is seen once per sprint, at the Thursday meeting.

1. **Sprint planning (team only):** the team records a `proposed` entry. The requirement is then
   *awaiting client*, and the team already works on it.
2. **During the sprint:** the team records `verified` entries: its own check result, with evidence;
   and, if needed, `revised` entries: the team changes the spec.
3. **Client meeting, for each requirement, in this order:** first the client's decision on the
   spec (`accepted` / `amended` / `rejected`), then the client's verdict on whether it was reached
   (`signed-off` ✅ / ⚠️ / ❌), judged against the spec as just accepted or amended.
4. **Anything not signed off ✅** is `carried-over` to a later delivery, or `dropped`.

The team writes everything. Client entries record what Konrad said, quoted or faithfully
paraphrased, with the date and the channel. Konrad never edits the files.

## A thread

```yaml
id: REQ-7
entries:
- date: 2026-11-16
  by: team
  type: proposed
  channel: sprint planning
  title: Short title for the tables
  statement: What the product must do.
  characteristic: Reliability
  metric: What is measured, and the threshold.
  why: The client need behind it.
  verification: How it is measured (script, test, manual review, CI).
  when: Before delivery
  owner: Team
  delivery: 2026-11-19
  recurring: false
  text: Why we propose it.
- date: 2026-11-18
  by: team
  type: verified
  channel: sprint
  result: ✅
  evidence: Commit `abc1234`, `scripts/quality/check_silver.py`.
  output: |
    $ python scripts/quality/check_silver.py
    RÉSULTAT                  : OK
  text: Run on the full corpus.
```

Every entry has `date` (YYYY-MM-DD), `by` (`team` or `client`), `type`, `channel` (sprint
planning, client meeting, Teams, mail…) and `text` (free Markdown). Entries reconstructed from the
old `QUALITY.md` carry `migrated: true`. Dates never go backwards within a thread.

| Entry type | By | Carries |
|---|---|---|
| `proposed` | team | Every requirement field (below), or only `title` and `statement` for a backlog item (see below). Always the first entry, and only once. |
| `revised` | team | Only the requirement fields that change, at least one. The team changes the spec; the client has to decide on it again. |
| `amended` | client | Only the requirement fields that change, at least one: what the client changed (e.g. threshold 0.90 → 0.95). |
| `accepted` | client | Nothing: the client agrees with the spec. |
| `rejected` | client | Nothing: the client refuses the spec. |
| `verified` | team | `result` (✅ / ⚠️ / ❌), `evidence` (links to commits, PRs, files), optional `output` (raw text, shown as a code block). |
| `signed-off` | client | `result` (✅ / ⚠️ / ❌): the client's verdict on whether the requirement was reached. |
| `carried-over` | either | `delivery`: the new target client meeting. The requirement stays open and its thread goes on. |
| `dropped` | either | Nothing: the requirement is abandoned. It leaves the current list but its thread is kept. |
| `note` | either | Text only. |

Requirement fields: `title` (short, for tables), `statement`, `characteristic` (ISO 25010:
Functional suitability, Performance efficiency, Compatibility, Usability, Reliability, Security,
Maintainability, Portability), `metric` (what is measured **and** the threshold), `why` (client
need), `verification` (how it is measured), `when` (free text: "Before delivery", "Each sprint",
"CI"…), `owner`, `delivery` (date of the targeted client meeting), `recurring` (checked every
sprint or in CI).

**Backlog.** A requirement the team wants to keep in view without committing to a delivery is
recorded as a `proposed` entry with no `delivery`. It then only needs a `title` and a
`statement`; its ID is reserved. When a sprint commits to it, the team records a `revised` entry
with the `delivery` and every requirement field still missing (validation refuses a thread
committed to a delivery with an incomplete spec). Until then it is listed in
[OVERVIEW.md](OVERVIEW.md) with the delivery *backlog*, but not in [CURRENT.md](CURRENT.md).

**Derived state.** The current spec is that of `proposed`, with every `revised` and `amended`
applied in order (a `carried-over` sets the delivery). The client status is *awaiting client*
until the client's first decision, then follows the latest `accepted` / `amended` / `rejected` /
`signed-off` / `dropped`; a `revised` puts the whole requirement back to *awaiting client*, even after a sign-off (a
dropped requirement stays dropped).
The latest result is that of the latest `verified` entry (⏳ if none). A requirement is **open**
until it is signed off ✅, rejected or dropped. [CURRENT.md](CURRENT.md) lists the open
requirements committed to a delivery, plus the recurring ones signed off ✅, so a regression still
shows up. Nothing depends on today's date.

## Reading the threads

A local tool shows the ledger as a conversation, for reading it alone or screen-sharing it at the
client meeting. From the repo root:

```
python scripts/quality/tool.py
```

It prints a local URL (`http://127.0.0.1:8765/`; another port with `--port`). It shows a
filterable table of every requirement, each requirement's page (current spec at the top, then
its thread as bubbles, team on the left, client on the right, spec changes shown before → after),
and one page per meeting (every entry dated on it, plus the meeting's own thread). It only reads:
it never writes a file and never runs git. If a file is invalid, it lists the errors instead.

## Recording an entry

1. Append the entry at the end of the thread's `entries` list (never edit or remove a past entry;
   fixing a genuine typo by hand is fine, git keeps the trace). A new requirement takes the next
   free `REQ-<n>` and starts with `proposed`. A meeting goes in `deliveries.yaml`.
2. Run, from the repo root:

   ```
   python scripts/quality/regenerate.py
   ```

   It rewrites the YAML files in their canonical form (fixed key order, multi-line text as `|`
   blocks, no comments: anything worth keeping goes in a `text` field), validates every file, and
   regenerates `CURRENT.md` and `OVERVIEW.md`. It exits with code 1 and lists the errors if a
   file is invalid; the views are then left untouched.
3. Commit the threads and the views together. CI (`pytest`) fails if a file is invalid or not
   canonical, or if a view is out of date.
