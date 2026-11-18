# Data & confidentiality rules

Moved from §4 of the former `QUALITY.md` (now removed), unchanged in substance.

- Data that must **never** be committed (paths, file types): `data/` (bronze, silver, gold and `state.json`) and `.env` (API keys).
- Where the data actually lives (who has access): generated locally by each teammate from the public English One Piece Fandom wiki (`python -m guess_arc.ingestion`). The source is public, under CC BY-SA, and used for academic purposes with attribution.
- Tools/services **not** allowed by the client: none so far. Sending chapter text (public wiki content) to the Anthropic API is allowed, with the key kept in `.env`.
- Personal data involved (GDPR) and how it is handled: none. The corpus only covers fictional characters.
- Matching `.gitignore` entries are in place: ☑ (`data/`, `.env`)
