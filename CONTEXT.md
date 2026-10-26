# One Piece Chapter Taxonomy

The domain for turning each One Piece chapter into structured, queryable data — what happened, to whom, and between whom — as input to chapter-event prediction.

## Language

### Structure

**Chapter Record**:
The tier of taxonomy fields that describe the chapter itself — mood, tension, locations, faction presence, and similar. Never used for something that happened to one specific character, or between characters.
_Avoid_: taxonomy (too broad — refers to the whole schema, not this tier)

**Character-in-Chapter Record**:
One character's attributes within a single chapter — health, emotional state, techniques revealed, powers used, death, bounty reveal, and similar. Anything that happened *to* one specific character belongs here, never as a Chapter Record field.
_Avoid_: character tag, per-character taxonomy

**Interaction**:
A relationship between two or more Characters and/or Factions within a chapter. Never a property of a single Character or of the chapter alone. `Fight` is the only Interaction type currently defined; the shape is designed so new types (e.g. a future `Alliance`) extend it without changing existing data.

**Schema Version**:
The version tag carried by every taxonomy record, allowing new fields or Interaction types to be added later without invalidating records tagged under an earlier version.

**Confidence**:
A 0-100 self-assessed certainty attached to one specific claim — a Duel's pairing, a single Character-in-Chapter attribute, etc. Always scoped to the claim it supports, never to a whole chapter.
_Avoid_: confidence_score (the old, chapter-wide meaning no longer applies)

### Identity

**Character**:
A uniquely identified individual, resolved to one canonical entity via its One Piece Wiki page regardless of how many name variants refer to it (e.g. "Luffy" and "Monkey D. Luffy" are the same Character; "Fake Luffy" is a different one).
_Avoid_: character name, character string

**Faction**:
A named group or crew treated as a participant in its own right (e.g. "Arlong Pirates"), identified the same way as a Character, for cases where no individual member is named.
_Avoid_: crew, group, team

**Character Registry**:
The canonical lookup from a Character to its identity: id, canonical name, known aliases, and source wiki page.

### Fights

**Fight**:
The Interaction type covering combat. Composed of one `Battle` plus zero or more nested `Duel`s, and identified by a `Fight ID` that stays stable across every chapter the fight spans.

**Battle**:
The unpaired shape of a Fight — a list of `Sides`, with no requirement that any two sides are paired 1:1. Covers both simple 1v1s (two sides) and multi-faction brawls (3+ sides).

**Side**:
One Battle-partitioned group of participants (Characters and/or Factions).

**Duel**:
An optional, strictly pairwise (exactly two participants) confrontation nested inside a Battle, asserted only when the source explicitly supports that specific pairing. Never inferred to fill in an unpaired Battle.

**Fight ID**:
The identifier linking every chapter's segment of the same ongoing Fight, so a fight spanning many chapters is one entity rather than disconnected per-chapter records.

**Fights Index**:
The canonical lookup, keyed by Fight ID, of which chapters/segments belong to a given Fight.

### Embeddings

**Silver File**:
The cleaned, per-chapter source document: a structured header (arc, Characters with Faction and on-panel flag) followed by the chapter's prose sections. The input from which both taxonomy records and Chapter Embeddings are derived.
_Avoid_: silver, chapter file, markdown file

**Gold Representation**:
A machine-learning-ready form of every chapter, derived from Silver Files and consumed by chapter-event prediction. Two coexist: the **Taxonomy Gold** (Chapter Records, Character-in-Chapter Records and Interactions — precise and interpretable, but costly to produce) and the **Embedding Gold** (one Chapter Embedding per chapter — cheap and complete, but not human-readable). Neither replaces the other; they're alternative inputs to the same prediction task.
_Avoid_: gold (alone — always say which one)

**Long Summary**:
The free-prose narrative section of a Silver File describing what happens in the chapter. Distinct from the Short Summary and the Chapter Notes, and from the structured header.

**Chapter Embedding**:
A single vector representing one chapter's Long Summary prose — and only that. Never encodes the structured header, so the cast of a chapter can't leak into it.
_Avoid_: chapter vector, summary vector

**Predicted Embedding**:
A Chapter Embedding forecast for chapter n+1 from the Chapter Embeddings of chapters up to n. Judged both directly against the real Chapter Embedding of n+1 and, once decoded, against the Characters listed in chapter n+1's Silver File header — a yardstick independent of both Gold Representations.
_Avoid_: next vector, forecast
