# Entity extraction: what we built, what we got, what we learned

*Version française : [entity-extraction.fr.md](entity-extraction.fr.md)*

- **Scope:** the entity extraction step, tickets ENT-01 to ENT-08 (#80–#87), PR #104, and follow-ups #105 and #106
- **State described:** branch `extraction/entities`, commit `7b88730`, full corpus run on 10 November 2026
- **Audience:** anyone who wants to understand the step without reading the code: teammates, the client, the jury

---

## 1. In short

For every chapter t of *One Piece*, we now know **which named things the reader has met so far**
(characters, crews, places, ships, Devil Fruits, weapons, objects), **under which names**, and
**how often they have been mentioned**. We call this list **Registry(t)**.

We build it without any AI model guessing names. Instead, we reuse the work the wiki's editors have
already done: every `[[link]]` in a chapter summary points to the exact wiki page of the thing it
names. That page title becomes the thing's unique identifier.

| What | Result |
|---|---|
| Chapters covered | 1 to 1193, all of them |
| Distinct entities | 2,534 |
| Mentions found | 67,923 (22,321 from links, 45,602 recovered by name matching) |
| Entities with no type (`Unknown`) | 1.35 % of Mentions |
| Precision proxy (are the names we match really in the chapter?) | **97.8 %**, target ≥ 80 % |
| Recall proxy (do we find every character who appears?) | **53.9 %**, target ≥ 95 %, see §6.1: mostly a limit of the source text, not of the extractor |
| Automated tests | 116, all passing, no network needed |

**The two things still open** are the low recall figure (§6.1) and the hand review of hidden
identities (§9, point 2).

---

## 2. Why this step exists

The project's goal is to predict which characters will appear in chapter n+1 from chapters 1 to n.
The model (a GRU, a sequence model) needs, for every chapter, a clean list of the things in it.
"Luffy", "Straw Hat" and "Monkey D. Luffy" must count as one character, and "Fake Luffy" must not.

One rule shapes the whole step (it is written down in
[ADR 0002](adr/0002-reader-knowledge-only.md)):

> **At chapter t, the model may only know what a reader knows at chapter t.**

If the input contains information from the future (a secret identity revealed 300 chapters later, a
nickname given later), the model's scores look good during testing but collapse in real use, when
the future is not available.

---

## 3. The vocabulary in one minute

The full glossary is in [CONTEXT.md](../CONTEXT.md). The words used in this document:

| Word | Meaning | Example |
|---|---|---|
| **Entity** | A named being, group, place or thing of the story | Luffy, the Straw Hat Pirates, Wano Country |
| **Canonical name** | The title of the Entity's English wiki page: its unique identifier | `Edward Newgate` |
| **Alias** | Any other name used for it in the text | "Whitebeard" |
| **Scene** | One paragraph of a chapter's Long Summary | |
| **Mention** | One occurrence of an Entity in a Scene | |
| **Cast** | The characters listed as present in a chapter's character table (CharTable) | |
| **Entity type** | One fixed category per Entity | Character, Group, Place, Ship, Devil Fruit, Weapon, Object, Unknown |
| **Title / Concept** | A rank or a general idea. **Never** an Entity | Admiral, Pirate, Haki |
| **Disguise** | A false identity presented to the reader as a different person, until the **Revelation** chapter | Kyoshiro is really Denjiro |
| **Registry(t)** | Every Entity known at chapter t, with its type and the Aliases used so far | |

---

## 4. The first attempt, and why we dropped it

In September 2026, the first version tried to **guess** entities from plain text:

1. spaCy (a general-purpose language tool) found names in the summaries and guessed their kind
   (person, place...).
2. An embedding model turned each name into a vector, and a clustering algorithm (HDBSCAN) grouped
   names that "looked alike" into one entity.

It did not work well, for reasons that come from the domain itself:

- **spaCy has never seen One Piece names.** It labelled *Zoro* and *Katakuri* as places because
  short, Japanese-sounding words look like place names to it. *Kaido* was also labelled a place.
- **Clustering merged unrelated names.** The vectors capture how a name *looks*, not what it
  *means*. *Ohara* ended up merged with 45 unrelated names, and six different kingdoms were merged
  into one.
- **Object detection grabbed the owner.** "Zoro's sword" produced an object called "Zoro". On the
  full corpus, 54 % of detected "objects" were actually character names.

Each fix (looking names up on the wiki, reclassifying with wiki categories, removing possessives)
pointed in the same direction: **the wiki already knows the answer.** In October we also measured
that tagging all chapters with free LLM APIs would not scale (about 5,000–7,000 tokens per chapter,
and daily quotas of a few dozen requests).

**Decision (26 October):** drop the guessing pipeline and its heavy dependencies, and rebuild
entity extraction on the wiki's own links, with fixed, readable rules.

---

## 5. How the extraction works today

```text
 bronze (raw wikitext of 1193 chapters)
   │
   ├─ 1. Long Summary  ──► Scenes (one per paragraph)
   ├─ 2. [[links]]     ──► Mentions + dated Aliases
   ├─ 3. name matching ──► Mentions the wiki did not link
   ├─ 4. CharTable     ──► Cast (who is present)
   ├─ 5. typing        ──► one Entity type per Entity
   ├─ 6. filtering     ──► Titles and Concepts removed
   └─ 7. Disguises     ──► hidden identities kept apart until their Revelation
   │
 gold/entities: registry.jsonl  +  registry_quality.json  +  disguise_candidates.csv
```

All of this lives in **one function**, `extract_entities(chapters, reference)`, in
`src/guess_arc/entities/extraction.py`. It reads nothing from disk and makes no network call: it
only receives data and returns a result. Everything that touches files or the wiki stays in
`pipeline.py`. This is why the 116 tests run in about one second, offline.

### Step 1: Scenes

Each paragraph of a chapter's Long Summary is a Scene. Sub-headings, bold titles and lone images
are not Scenes.

### Step 2: links give Mentions and Aliases

On the wiki, `[[Edward Newgate|Whitebeard]]` displays "Whitebeard" and links to the page
*Edward Newgate*. So we get, for free and without guessing:

- a **Mention** of `Edward Newgate`;
- an **Alias**, "Whitebeard", **dated** by the first chapter where it is used. Before that chapter,
  the Alias does not exist in Registry(t). For example, "Lucy" is not an Alias of Sabo before the
  Dressrosa arc.

Not every link text is a name: `[[Marshall D. Teach|man]]`, `[[Kouzuki Hiyori|his daughter]]`. Link
text becomes an Alias only if it starts with a capital letter and its first word is not in a list of
common words (`common_words.txt`).

A link to a part of a page usually names that part: `[[Gomu Gomu no Mi/Gear 5 Techniques|Gear 5]]`
counts as a Mention of the parent page, *Gomu Gomu no Mi*, and never creates an Alias. Two kinds of
links break that rule (#106), and the wiki's own categories tell them apart:

- **A subpage that is a thing of its own.** The six Vegapunk satellites live on subpages of
  *Vegapunk* (`Vegapunk/Lilith`), but each subpage has its own categories (*Female Characters*,
  *Satellites*). When a subpage's categories give an Entity type, it is an Entity of its own, named
  by its full title: `[[Vegapunk/Lilith|Lilith]]` is a Mention of `Vegapunk/Lilith` (Character) with
  the Alias "Lilith". A subpage with no category (`Haki/Armament Haki`) stays a part of its parent.
- **An entry of a catalog.** *Animal Species*, *Plant and Fungi Species* and *Foods* are list pages
  (category `Lists`): each section describes a different species or dish. A link to one of these
  sections is a Mention of the entry, named by the section, which is also the title of the wiki's
  redirect: `[[Animal Species/Arabasta Saga#Bananawani|Bananawani]]` and `[[Bananawani]]` are the
  same Entity, typed by the catalog's categories (Object). The catalog itself (`[[Animal
  Species|Animals]]`) is not an Entity, like a Concept. Entries of a catalog that is itself excluded
  (`Marine Ranks#Commodore`, a Title) are excluded too.

### Step 3: finding the names the wiki did not link

**Problem:** the wiki only links a name the first time it appears on a page. In chapter 1000,
"Luffy" is linked once and then written as plain text a dozen times.

**Solution (Alias match):** in each Scene, search for the Canonical names and already-dated Aliases
of the Entities **linked somewhere in the same chapter**. Safety rules:

- **Case-sensitive:** "Queen" (the character) matches, "queen" (the word) does not.
- **Only Entities linked in this chapter:** "Queen" is not searched in a chapter where the character
  Queen is never linked. This prevents most false matches.
- **Longest name first**, and a name shared by two Entities linked in the same chapter is ignored.

Result: two thirds of all Mentions (45,602 out of 67,923) come from this step.

### Step 4: the Cast from the character table

Each chapter page has a character table listing who appears, marked as present, in flashback
(*Recall*) or only on the cover page (*Cover appearance*). Every listed character enters
Registry(t) at that chapter, **even if the summary never names them**. A linked faction heading
(`;[[Straw Hat Pirates]]`) adds the Group to Registry(t) without counting as a Mention.

### Step 5: one type per Entity

Each Entity gets **exactly one type for the whole story**, decided in this order:

1. **Manual overrides** (`reference/type_overrides.csv`, 6 entries) beat everything. They settle
   borderline cases by the Entity's main role in the story: Wano Country is a Place (not a regime),
   Zunesha is a Character (and Zou, on its back, is a separate Place).
2. **Local datasets** (`reference/characters.json`, `islands.json`, `devil_fruits.json`), after
   cleaning the names: `Edward Newgate [Whitebeard]` → Edward Newgate, `Scien [Queen]` → Queen, the
   English name of a Devil Fruit → its Japanese name.
3. **Wiki categories**, read from the wiki page and mapped by ordered rules: `Pirate Crews` → Group,
   `Ships` → Ship, `Swords` → Weapon, `Locations` → Place... The order matters: Devil Fruit is checked
   before Character, so *Gomu Gomu no Mi* is not typed as a person. Categories are fetched once and
   saved in `reference/wiki_categories.json`, so later runs make no network call and always give the
   same result.
4. Otherwise: **Unknown**.

Only the names and types are taken from the datasets. Their other fields (affiliation, bounty,
alive/dead, relations) describe the story at its latest chapter: using them would leak the future.

### Step 6: Titles and Concepts are removed

"Admiral", "Pirate" or "Haki" are linked very often but are not Entities. They are removed:

- by wiki category: a page in `Positions` or `Occupations` is a Title (Rear Admiral, Shogun, Cook);
  a page in `Terms` is a Concept (Jolly Roger, Epithet), unless another category makes it a Group;
- by the hand-written list `reference/concepts.txt`, for the cases the categories miss.

Wiki redirects listed in `reference/redirects.csv` are merged into their target:
"Eleven Supernovas" becomes an Alias of *Worst Generation* instead of a second Entity.

### Step 7: Disguises

The wiki writes `[[Denjiro|Kyoshiro]]` from the very first appearance of Kyoshiro, although the
reader only learns that Kyoshiro is Denjiro much later. Taking links at face value would leak that
secret.

- The extraction lists **Disguise candidates**: character Aliases that share no word with their
  Canonical name (Kyoshiro → Denjiro, Miss All Sunday → Nico Robin), sorted by number of links, in
  `data/gold/entities/disguise_candidates.csv`.
- A Disguise merges two Entities the reader already knows. `named_apart_from` is the first chapter
  where the Long Summary or CharTable names the character under its own name without the Alias,
  before `named_together_from`, the first chapter that links both (often the Revelation). When
  `named_apart_from` is empty, the real name only comes with the Alias: a name revelation (Miss All
  Sunday → Nico Robin), not a Disguise.
- A human confirms the real ones and writes down the **Revelation** chapter in
  `reference/disguises.csv`.
- Before its Revelation, a confirmed Disguise is a separate Entity, with its own Mentions. From the
  Revelation on, it merges into the real character and becomes one of their Aliases.

### What the output looks like

`data/gold/entities/registry.jsonl` has one line per Entity and per change, valid from `valid_from` to
`valid_to` (`null` = still valid). `catalog` names the catalog page an Entity is an entry of
(`"Animal Species"` for Bananawani), `null` for every other Entity; like the type, it never changes:

```json
{"canonical_name": "Anjo", "entity_type": "Character", "catalog": null, "aliases": [],
 "valid_from": 1, "valid_to": null, "first_chapter_seen": 1,
 "last_chapter_seen": 1, "mention_count": 0}
```

`data/gold/entities/registry_quality.json` holds the quality measures used in §6 and lists for manual review
(the most suspicious Aliases, the 50 most mentioned Entities with their type, the remaining Unknown
Entities, the names excluded by category).

---

## 6. Results

Full corpus run, 10 November 2026, commit `7b88730`.

| Measure | Value | Target | Status |
|---|---|---|---|
| Chapters with at least one Scene | 1193 / 1193 (5,776 Scenes) | all | ✅ |
| Distinct Entities | 2,534 | | |
| Registry rows | 40,792 | | |
| Mentions | 67,923 (33 % links, 67 % name matching) | | |
| Precision proxy | 97.8 % | ≥ 80 % | ✅ |
| Recall proxy | 53.9 % | ≥ 95 % | ❌, see §6.1 |
| Mentions typed Unknown | 1.35 % | as low as possible | ✅ |
| Names excluded as Title/Concept by category | 73 | | |
| Tests | 116 passed, offline | all pass | ✅ |

**Entities by type:**

| Character | Place | Group | Devil Fruit | Object | Weapon | Ship | Unknown |
|---|---|---|---|---|---|---|---|
| 1,587 | 264 | 159 | 142 | 92 | 61 | 47 | 182 |

**How the Unknown share went down:**

| Stage | Mentions typed Unknown | Entities |
|---|---|---|
| Local datasets only (ENT-05) | 17.2 % | |
| + wiki categories and overrides (ENT-06) | 1.64 % | 2,623 |
| + Titles excluded by category (#105) | 1.46 % | 2,576 |
| + generic terms excluded, redirects merged (`7b88730`) | 1.35 % | 2,534 |
| + subpages and catalog entries resolved (#106) | 1.33 % | 2,598 |

The 50 most mentioned Entities and their types were all checked by hand: all correct.

### 6.1 Why the recall proxy is low

**What it measures:** among the characters the character table marks as present in a chapter, the
share that also have a Mention in that chapter's Long Summary.

**What we found** (quick measurement, 10 November 2026, on all 22,434 on-panel Appearances):

| Case | Share of Appearances |
|---|---|
| Linked in the summary | 53 % |
| Not linked, but the full name is in the text | 4 % |
| Not linked, but part of the name is in the text | 4 % |
| **The name is nowhere in the summary** | **39 %** |

**In about 39 % of cases, the summary simply never names the character.** Character tables list
everyone drawn in the chapter, including people in the background, while the summary tells the
story in a few paragraphs. No extractor that reads only the summary can go above about 61 %.

Two consequences:

- **The 95 % target was set against the wrong reference.** The recall proxy mostly measures how
  complete the wiki's summaries are, not how good the extractor is. The real room for improvement
  is the 4–8 % of names that are in the text but not matched: name matching only searches for
  Entities linked in the same chapter (a deliberate safety rule, §5 step 3).
- **Registry(t) does not miss these characters.** They enter it anyway through the character table
  (step 4). What they lack is a Mention, i.e. a place in a specific Scene.

The worst arcs are those with large battles and crowds: Marineford (27 %), Amazon Lily (33 %),
Post-War (35 %). The best are early arcs with few characters: Syrup Village (78 %), Thriller Bark
(76 %).

**Decision needed:** redefine the target (for example, measure recall only on characters whose name
appears in the summary), or keep the current measure and accept it as a description of the source.
This is a team decision about the quality requirement (REQ-12), not a code change.

### 6.2 Precision: the names we match are right

97.8 % of matched character names fall on a character who is in that chapter's Cast. The
"suspicious" Aliases at the top of the list are mostly characters who are **talked about** without
being present: "Big Mom" (66 of 613 matches outside the Cast), "Kaidou" (58 of 525), "Whitebeard",
"Roger". These are correct Mentions; they are not errors.

### 6.3 Subpages and catalogs (#106)

Full corpus run, 12 November 2026, compared with the same reference files before the change.

| Measure | Before | After |
|---|---|---|
| Mentions of *Vegapunk* | 578 | 442 |
| Vegapunk satellites in Registry(t) | 0 | 6 Characters (Shaka 84, Lilith 81, York 55, Atlas 50, Edison 41, Pythagoras 26 Mentions) |
| Other subpages of their own | 0 | 11 Weapons (Clima-Tacts, Battle Frankies, Usopp's Kabuto and Pachinko) |
| `Animal Species`, `Plant and Fungi Species`, `Foods` as Entities | 40, 4 and 24 Mentions | absent |
| Catalog entries | 0 | 62 (44 animals, 14 foods, 3 plants, 1 technology) |
| Distinct Entities | 2,535 | 2,598 |

Catalogs found: *Animal Species*, *Plant and Fungi Species*, *Foods* and *Technology*. *Marine Base*
is also a catalog, but its only section link points to a list heading, so it adds no entry.

---

## 7. Problems we hit, and what we did

| Problem | Example | What we did |
|---|---|---|
| A general NLP tool does not know One Piece names | Zoro labelled as a place | Stopped guessing: use wiki links, which editors already resolved |
| Grouping names by similarity merges unrelated things | *Ohara* merged with 45 names | Same: identity is the wiki page title, no clustering |
| The wiki links a name only once per page | "Luffy" linked once in ch. 1000 | Alias match, limited to Entities linked in the same chapter, case-sensitive |
| Link text is not always a name | `[[Marshall D. Teach\|man]]` | Capital letter + common-word list; the link still counts as a Mention |
| The wiki reveals secret identities from day one | `[[Denjiro\|Kyoshiro]]` | Disguise candidates, human confirmation, Revelation chapter |
| Datasets only cover characters, islands and Devil Fruits | crews, ships, swords all Unknown (17.2 %) | Wiki categories with ordered rules, cached locally |
| Dataset names do not always match wiki titles | `Cutty Flam [Franky]` vs `Franky` | Name cleaning; bracketed epithet used as a name |
| Some Entities fit two types | Wano Country: place and regime | One type by main role in the story; manual override file |
| Ranks and general words became Entities | Rear Admiral, Cook, Jolly Roger | Excluded by wiki category (`Positions`, `Occupations`, `Terms`) + `concepts.txt` |
| Generic weapon classes share categories with named weapons | Katana, Firearm | Added to `concepts.txt` by hand |
| Two wiki titles for one thing | Eleven Supernovas / Worst Generation | `redirects.csv`: the redirect becomes an Alias |
| A subpage moved on the wiki keeps its old title as a redirect | `Usopp's Arsenal/Kabuto` and `Usopp Tactics/Kabuto`, the same weapon | Old titles added to `redirects.csv` |
| Separate things live on subpages | the six Vegapunk satellites merged into Vegapunk (578 Mentions), York missing | A subpage whose own categories give a type is its own Entity, named by its full title |
| List pages swallow their entries | a fake Entity `Animal Species` (40 Mentions); Bananawani lost | A section of a `Lists` page is an entry named by the section; the list page is dropped |
| A list page and a redirect to one of its entries have the same categories | `News Coo` is in `Lists` like `Animal Species` | A page is a catalog only if the corpus links to one of its sections or subpages |
| A catalog section can carry the title of another page | `Animal Species/Arabasta Saga#Arabasta` (a heading) merged into the kingdom; `Foods#Candy` into the Character Candy | A section titled like a page of its own (not a redirect into the catalog) designates nothing: the link is dropped |
| Dataset fields describe the end of the story | bounty, affiliation, alive/dead | Never read: only names and types are used |
| Tests could not import the code without installing it | `ModuleNotFoundError` | `pythonpath = ["src"]` in the pytest config |

---

## 8. Decisions and why

| Decision | Why | What we rejected |
|---|---|---|
| **Use the English wiki only** ([ADR 0001](adr/0001-source-wiki-fandom-anglais.md)) | Complete for all chapters, filled about 70 minutes after release, stable format | French wiki (stopped updating), Japanese sources (no structure) |
| **The wiki page title is the identity** | Editors have already resolved who is who; no guessing, no model | spaCy + clustering (§4), LLM tagging (does not scale on free tiers) |
| **Only reader knowledge at chapter t** ([ADR 0002](adr/0002-reader-knowledge-only.md)) | Future information would inflate test scores and fail in production | Using the datasets' full character sheets |
| **Aliases dated by first use** | "Lucy" must not be Sabo before the reader knows it | Undated Alias lists |
| **Name matching only for Entities linked in the same chapter** | Keeps precision high (97.8 %) | Searching every known name everywhere: many false matches ("Queen", "Roger") |
| **One fixed type per Entity** | A simple, stable input for the model | Types that change over time |
| **Fixed priority order: override > dataset > wiki category > Unknown** | Predictable; a human can always have the last word | Voting or scoring between sources |
| **Titles and Concepts are never Entities** | "Admiral" is held by many people over time; it is an attribute | Treating ranks as Groups |
| **Borderline names excluded on purpose** (Royal Guards, Mountain Bandits, New Age, Pantri) | Their wiki pages describe a role or idea, not one specific group; an override can bring them back | Keeping them as Unknown Entities |
| **A separate subpage keeps its full title** (`Vegapunk/Lilith`) | It is the wiki's page title, so the identity stays unique; the short name is its Alias | Short names ("Lilith"), which may clash with other pages |
| **A catalog entry is named by its section** (`Bananawani`) | Same name as the wiki's redirect, so a direct link and a section link give one Entity | Full anchor (`Animal Species/Arabasta Saga#Bananawani`) |
| **Catalogs found from the wiki's `Lists` category, not by hand** | No list to maintain; `Dials` waits (see §9) | A hand-written catalog list |
| **Wiki categories cached in the repo** | Same result on every run, works offline, reproducible by someone else | Querying the wiki on every run |
| **Disguises confirmed by a human** | Automatic detection proposes, a person decides; a false Disguise would split one character in two | Fully automatic detection |
| **Disguises for Characters only (v1)** | Most of the value, least of the effort; the leak for other types is accepted | All Entity types |
| **One pure function, all I/O outside** | Fast offline tests on real wiki excerpts; easy to reason about | Extraction mixed with file and network access |
| **The current wiki text is used for the 1193 past chapters** | It is the only version we have; later edits may add hindsight wording, an accepted and documented limit | Rebuilding each page's first revision |

---

## 9. Known limits and next steps

1. **Recall target (§6.1).** Decide how REQ-12 should measure recall. Optionally, try matching
   names of characters in the chapter's Cast even if they are not linked in the summary, and
   measure whether precision holds.
2. **Disguise review not done yet.** `reference/disguises.csv` is still empty, so **today's
   Registry(t) still leaks secret identities** (Kyoshiro is counted as Denjiro from his first
   appearance). 197 candidates are waiting in `data/gold/entities/disguise_candidates.csv`; the 72
   with no `named_apart_from` are name revelations and can be rejected. Many others are plain
   epithets ("Big Mom" → Charlotte Linlin, "Kizaru" → Borsalino) and must be rejected too; the real
   ones (Kyoshiro, Komurasaki, Kamazo...) need their Revelation chapter.
3. **182 Entities remain Unknown** (1.35 % of Mentions). Most are deliberately untyped notions:
   peoples and tribes (Shandia, Mink Tribe), fighting styles (Three Sword Style), events (Buster
   Call, Levely). We should decide whether they need a type or should be excluded like Concepts.
4. **Hindsight in old summaries.** Past chapter texts are the current wiki version and may contain
   wording written after later reveals (ADR 0002, accepted limit).
5. **Dataset names are never checked against wiki categories.** A Title present in a dataset would
   not be excluded. A manual check found none.
6. **`Dials` stays merged.** It is laid out like a catalog (Impact Dial, Reject Dial, Jet Dial are
   sections, 40 Mentions) but is not in the `Lists` category, so its entries still count as Mentions
   of `Dials`. Fixing it needs a hand-written catalog list, left out on purpose (#106).
7. **Catalog entries are as clean as the wiki's section titles.** A few are headings or variants:
   `Other Varieties 2` (Foods), `Kung Fu Dugongs` next to `Kung-Fu Dugongs`. Redirects not linked
   through a section (`Weather Ball`, `Mizu Mizu Meat`) are still Entities but have `catalog: null`.

---

## 10. How to rerun it

```bash
python -m guess_arc.entities            # whole corpus; fetches only uncached wiki categories
python -m guess_arc.entities --offline  # no network at all
pytest                                  # 127 tests, offline
```

| File | Role | Edited by |
|---|---|---|
| `src/guess_arc/entities/extraction.py` | All the rules (pure function) | code |
| `src/guess_arc/entities/pipeline.py` | Reads bronze, fetches categories, writes gold | code |
| `reference/type_overrides.csv` | Types set by hand | human |
| `reference/concepts.txt` | Titles and Concepts excluded by hand | human |
| `reference/redirects.csv` | Wiki redirects merged into their target | human |
| `reference/disguises.csv` | Confirmed Disguises and their Revelation chapter | human |
| `reference/wiki_categories.json` | Cache of wiki categories | pipeline |
| `data/gold/entities/registry.jsonl` | Registry(t) | pipeline |
| `data/gold/entities/registry_quality.json` | Quality report | pipeline |
| `data/gold/entities/disguise_candidates.csv` | Disguise candidates to review | pipeline |

More details: [README](../README.md#entity-extraction), vocabulary in [CONTEXT.md](../CONTEXT.md).
