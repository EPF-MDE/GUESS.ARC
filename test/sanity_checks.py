"""Validation rules for the bronze/silver sanity check (issue #4).

Pure functions only — no filesystem or network access — so they can be unit
tested against synthetic fixtures and reused by the integration tests that
walk the real `data/bronze/` and `data/silver/` directories.
"""
import re

TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def validate_bronze_record(record, line_no):
    """Return a list of human-readable errors for one bronze JSONL record."""
    errors = []

    def prefix(msg):
        return f"line {line_no}: {msg}"

    if not isinstance(record, dict):
        return [prefix(f"expected a JSON object, got {type(record).__name__}")]

    for field, expected_type in (("number", int), ("revid", int), ("wikitext", str)):
        if field not in record:
            errors.append(prefix(f"missing field '{field}'"))
        elif not isinstance(record[field], expected_type) or isinstance(record[field], bool):
            errors.append(
                prefix(f"field '{field}' should be {expected_type.__name__}, "
                       f"got {type(record[field]).__name__}")
            )

    if "number" in record and isinstance(record["number"], int) and record["number"] <= 0:
        errors.append(prefix(f"field 'number' should be positive, got {record['number']}"))

    if "wikitext" in record and isinstance(record["wikitext"], str) and not record["wikitext"].strip():
        errors.append(prefix("field 'wikitext' is empty"))

    if "timestamp" not in record:
        errors.append(prefix("missing field 'timestamp'"))
    elif not isinstance(record["timestamp"], str) or not TIMESTAMP_RE.match(record["timestamp"]):
        errors.append(prefix(f"field 'timestamp' is not ISO-8601 UTC, got {record.get('timestamp')!r}"))

    return errors


def validate_silver_content(text, filename):
    """Return a list of human-readable errors for one silver chapter file."""
    errors = []

    def prefix(msg):
        return f"{filename}: {msg}"

    match = FRONT_MATTER_RE.match(text)
    if not match:
        return [prefix("missing YAML front-matter (no leading '---' ... '---' block)")]

    front_matter = match.group(1)
    body = text[match.end():]

    if not re.search(r"^chapter:\s*\d+\s*$", front_matter, re.MULTILINE):
        errors.append(prefix("front-matter missing numeric 'chapter:' field"))

    if not re.search(r'^title:\s*\S', front_matter, re.MULTILINE):
        errors.append(prefix("front-matter missing 'title:' field"))

    if not re.search(r'^arc:\s*\S', front_matter, re.MULTILINE):
        errors.append(prefix("front-matter missing 'arc:' field"))

    if not re.search(r"^characters:\s*$", front_matter, re.MULTILINE):
        errors.append(prefix("front-matter missing 'characters:' list"))
    elif not re.search(r"^\s*-\s*name:\s*\S", front_matter, re.MULTILINE):
        errors.append(prefix("'characters:' list has no entries with a 'name'"))

    for section in ("Short Summary", "Long Summary", "Chapter Notes"):
        if not re.search(rf"^##\s*{re.escape(section)}\s*$", body, re.MULTILINE):
            errors.append(prefix(f"missing '## {section}' section"))

    return errors
