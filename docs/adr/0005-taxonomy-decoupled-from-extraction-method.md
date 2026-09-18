# Taxonomy schema is decoupled from the extraction method

Konrad's POC tagged chapters via a single zero-shot LLM call per chapter, reading only the wiki summary. This design doc defines what the taxonomy captures, not how it gets populated: we deliberately do not assume the eventual tagger is LLM-based, so the team can try LLM-based, rule-based/NLP, or hybrid extraction methods against the same schema without redesigning it per method.

The one schema-level consequence of this: `Confidence` is kept as a generic, method-agnostic signal (modeled after Konrad's `confidence_score`, already validated at 94% precision on booleans) attached to individual claims — a Character-in-Chapter attribute, a Duel's pairing — rather than a mechanism that assumes an LLM is self-reporting it. Whatever method eventually populates a record is expected to populate this signal by whatever means fits it (an LLM's self-assessment, a rule-based match score, a human review flag).
