# Taxonomy schema — target design

This is the concrete shape of the redesigned taxonomy from issue #2. For the vocabulary, see `CONTEXT.md`; for why each part is shaped this way, see `docs/adr/`. This document is the plain "what it looks like" the ADRs and glossary don't spell out on their own.

Three files per chapter/corpus, replacing Konrad's single `chapters_tagged.json`:

- `data/taxonomy/chapter_NNNN.json` — one per chapter
- `data/taxonomy/fights_index.json` — one entry per Fight, across all chapters
- `data/characters/registry.json` — one entry per Character/Faction, across all chapters

## 1. Chapter taxonomy file

`data/taxonomy/chapter_0082.json`:

```json
{
  "schema_version": 1,
  "chapter": {
    "number": 82,
    "arc": "Arlong Park Arc",
    "chapter_mood": "tense",
    "tension_level": 8,
    "locations": ["Arlong Park"],
    "location_change": false,
    "sea_region": "East Blue",
    "cliffhanger_type": "battle_escalation",
    "marines_present": false,
    "yonko_present": false,
    "yonko_name": null,
    "shichibukai_present": false,
    "world_government_present": false,
    "revolutionary_army_present": false,
    "road_poneglyph_found": false,
    "ancient_weapon_mentioned": false,
    "will_of_d_mentioned": false,
    "color_spread": false,
    "new_arc_starts": false,
    "arc_ends": false,
    "new_alliance_formed": false,
    "confidence": 92
  },

  "characters": [
    {
      "character_id": "monkey-d-luffy",
      "role": "protagonist",
      "affiliation": "straw-hat-pirates",
      "health_state": "healthy",
      "emotional_state": "determined",
      "technique_revealed": null,
      "haki_used": [],
      "power_used": "Gomu Gomu no Mi",
      "dies": false,
      "death_type": null,
      "bounty_revealed": false,
      "major_decision": true,
      "arc_goal_progress": "progressing",
      "has_flashback": false,
      "confidence": 90
    },
    {
      "character_id": "roronoa-zoro",
      "role": "protagonist",
      "affiliation": "straw-hat-pirates",
      "health_state": "injured",
      "emotional_state": "determined",
      "technique_revealed": null,
      "haki_used": [],
      "power_used": null,
      "dies": false,
      "death_type": null,
      "bounty_revealed": false,
      "major_decision": false,
      "arc_goal_progress": "progressing",
      "has_flashback": false,
      "confidence": 88
    }
  ],

  "interactions": [
    {
      "type": "fight",
      "fight_id": "fight-0034",
      "battle": {
        "sides": [
          ["monkey-d-luffy"],
          ["arlong"]
        ]
      },
      "duels": [
        {
          "participants": ["roronoa-zoro", "hatchan"],
          "confidence": 85
        },
        {
          "participants": ["sanji", "kuroobi"],
          "confidence": 80
        }
      ],
      "ends_this_chapter": false,
      "winner": null
    }
  ]
}
```

Notes:

- `characters[]` lists every Character-in-Chapter Record for that chapter. `character_id` and `affiliation` reference the Character Registry / Faction, not free-text names.
- `interactions[]` holds every Interaction in the chapter (currently only `type: "fight"` is defined, per ADR 0005). A chapter can have multiple `interactions` entries — e.g. a chapter with two unrelated fights is two entries, each with its own `fight_id`.
- `battle.sides` is a list of lists (N-ary — 2 sides for a simple fight, 3+ for a Marineford-style brawl). Each entry in a side is a `character_id` or a `faction_id` (e.g. `"arlong-pirates"` for an unnamed group combatant).
- `duels` is optional and only present when the source text supports a specific pairing — it is not required to cover every participant in `battle.sides`.
- Chapter 82's real fight actually continues through chapter 89, so chapters 83-89 would each carry their own `interactions` entry with the *same* `fight_id: "fight-0034"` and progressively update `ends_this_chapter`/`winner` once it resolves.

## 2. Fights index

`data/taxonomy/fights_index.json`:

```json
{
  "fight-0034": {
    "label": "Straw Hats vs. Arlong Pirates (Arlong Park)",
    "chapters": [81, 82, 83, 84, 87, 88, 89],
    "sides": [
      ["monkey-d-luffy", "roronoa-zoro", "sanji", "usopp"],
      ["arlong-pirates"]
    ],
    "resolved": true,
    "winner": ["monkey-d-luffy", "roronoa-zoro", "sanji", "usopp"]
  }
}
```

One entry per `Fight ID`. Built/updated by scanning chapter files as they're tagged — this is the thing that lets "show me the whole Luffy vs. Crocodile fight" be a single lookup instead of scanning every chapter file.

## 3. Character registry

`data/characters/registry.json`:

```json
{
  "monkey-d-luffy": {
    "canonical_name": "Monkey D. Luffy",
    "aliases": ["Luffy", "Straw Hat Luffy", "Fifth Emperor"],
    "wiki_url": "https://onepiece.fandom.com/wiki/Monkey_D._Luffy"
  },
  "fake-luffy": {
    "canonical_name": "Fake Luffy",
    "aliases": [],
    "wiki_url": "https://onepiece.fandom.com/wiki/Fake_Luffy"
  },
  "arlong-pirates": {
    "canonical_name": "Arlong Pirates",
    "aliases": ["Arlong's crew", "the fish-men"],
    "wiki_url": "https://onepiece.fandom.com/wiki/Arlong_Pirates"
  }
}
```

Same shape for both Characters and Factions (ADR 0003) — a Faction is just an entry whose members are people rather than one person. **Not populated as part of issue #2** — resolving the corpus's 811 existing name variants to registry entries is separate follow-up work; this file only needs to exist with this shape once that work starts.

## What's deliberately not specified here

Per ADR 0005, how any of these three files gets *populated* (LLM prompt, rule-based extraction, hybrid, manual review) is out of scope — this document only fixes what the output looks like once something populates it.
