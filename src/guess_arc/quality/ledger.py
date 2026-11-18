"""Quality ledger: load, validate, replay and render a `quality/` folder.

Each quality requirement is a thread (`requirements/REQ-<n>.yaml`): an
append-only, dated list of entries between the team and the client. The threads
are the single source of truth; `CURRENT.md` and `OVERVIEW.md` are generated
from their replay. Meetings live in `deliveries.yaml`.

Public interface:
    validate(folder)      -> list of errors (empty when the folder is valid)
    replay(folder)        -> current state of every requirement
    render_current(reqs)  -> text of CURRENT.md
    render_overview(reqs) -> text of OVERVIEW.md
    canonicalise(folder)  -> rewrites the YAML files in canonical form
    regenerate(folder)    -> canonicalise, validate, write both views
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

REQUIREMENTS_DIR = "requirements"
DELIVERIES_FILE = "deliveries.yaml"

# What a requirement is made of: carried in full by `proposed`.
REQUIREMENT_FIELDS = (
    "title", "statement", "characteristic", "metric", "why",
    "verification", "when", "owner", "delivery", "recurring",
)

# Canonical key order of each kind of mapping. Unknown keys go last (and are
# reported by validate()).
THREAD_KEYS = ("id", "entries")
ENTRY_KEYS = ("date", "by", "type", "channel", "migrated", *REQUIREMENT_FIELDS,
              "result", "evidence", "output", "text")
DELIVERIES_KEYS = ("deliveries",)
MEETING_KEYS = ("date", "theme", "thread")
NOTE_KEYS = ("date", "by", "channel", "migrated", "text")

ID_RE = re.compile(r"REQ-[1-9]\d*")
AUTHORS = ("team", "client")
RESULTS = ("✅", "⚠️", "❌")
CHARACTERISTICS = (
    "Functional suitability", "Performance efficiency", "Compatibility", "Usability",
    "Reliability", "Security", "Maintainability", "Portability",
)
COMMON_REQUIRED = ("date", "by", "type", "channel", "text")
# Entry type -> (who records it, None if either; required fields; optional fields).
ENTRY_TYPES = {
    "proposed": ("team", REQUIREMENT_FIELDS, ()),
    "accepted": ("client", (), ()),
    "rejected": ("client", (), ()),
    "verified": ("team", ("result", "evidence"), ("output",)),
    "signed-off": ("client", ("result",), ()),
    "note": (None, (), ()),
}


# --- Canonical YAML ----------------------------------------------------------


class _Dumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        # Equal values shared between entries (a date, say) are written out each time.
        return True


def _represent_str(dumper, value):
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _represent_str)


def _dump(data) -> str:
    # No line folding: one line per scalar value keeps hand edits and diffs simple.
    return yaml.dump(data, Dumper=_Dumper, sort_keys=False, allow_unicode=True,
                     width=float("inf"))


def _ordered(mapping, keys):
    if not isinstance(mapping, dict):
        return mapping
    known = {k: mapping[k] for k in keys if k in mapping}
    return {**known, **{k: v for k, v in mapping.items() if k not in known}}


def _ordered_items(items, keys):
    return [_ordered(i, keys) for i in items] if isinstance(items, list) else items


def _canonical_data(path: Path, data):
    """`data` with every mapping in its canonical key order."""
    if not isinstance(data, dict):
        return data
    if path.name == DELIVERIES_FILE:
        data = _ordered(data, DELIVERIES_KEYS)
        meetings = _ordered_items(data.get("deliveries"), MEETING_KEYS)
        if isinstance(meetings, list):
            meetings = [
                {**m, "thread": _ordered_items(m["thread"], NOTE_KEYS)}
                if isinstance(m, dict) and "thread" in m else m
                for m in meetings
            ]
        return {**data, "deliveries": meetings} if "deliveries" in data else data
    data = _ordered(data, THREAD_KEYS)
    if "entries" in data:
        data["entries"] = _ordered_items(data["entries"], ENTRY_KEYS)
    return data


def _canonical_text(path: Path, data) -> str:
    return _dump(_canonical_data(path, data))


def _yaml_files(folder: Path) -> list[Path]:
    files = sorted((folder / REQUIREMENTS_DIR).glob("*.yaml"))
    deliveries = folder / DELIVERIES_FILE
    return files + [deliveries] if deliveries.exists() else files


def _read(path: Path) -> str:
    # Text mode turns CRLF into LF: a Windows checkout reads the same as Linux.
    return path.read_text(encoding="utf-8")


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def canonicalise(folder: Path) -> list[Path]:
    """Rewrite every parseable YAML file of `folder` in canonical form.

    Returns the files that changed. Files that don't parse are left alone
    (validate() reports them).
    """
    changed = []
    for path in _yaml_files(folder):
        text = _read(path)
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError:
            continue
        canonical = _canonical_text(path, data)
        if canonical != text:
            _write(path, canonical)
            changed.append(path)
    return changed


# --- Validation --------------------------------------------------------------


def _is_date(value) -> bool:
    # datetime is a subclass of date: a timestamp is not a valid entry date.
    return type(value) is dt.date


def _is_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _check_value(key: str, value) -> str | None:
    """Error for one field value, or None if it is well-typed."""
    if key in ("date", "delivery"):
        return None if _is_date(value) else f"{key} {value!r} is not an ISO date (YYYY-MM-DD)"
    if key == "recurring":
        return None if isinstance(value, bool) else f"recurring {value!r} is not true/false"
    if key == "migrated":
        return None if value is True else "migrated must be true when present"
    if key == "by":
        return None if value in AUTHORS else f"by {value!r} is not one of {', '.join(AUTHORS)}"
    if key == "characteristic":
        return None if value in CHARACTERISTICS else (
            f"characteristic {value!r} is not an ISO 25010 characteristic "
            f"({', '.join(CHARACTERISTICS)})")
    if key == "result":
        return None if value in RESULTS else f"result {value!r} is not one of {' '.join(RESULTS)}"
    return None if _is_text(value) else f"{key} must be non-empty text"


def _check_fields(mapping: dict, required, optional) -> list[str]:
    errors = [f"missing field '{k}'" for k in required if k not in mapping]
    allowed = set(required) | set(optional)
    errors += [f"unexpected field '{k}'" for k in mapping if k not in allowed]
    errors += [e for k, v in mapping.items() if k in allowed
               if (e := _check_value(k, v)) is not None]
    return errors


def _check_keys(mapping: dict, keys) -> list[str]:
    """Missing and unexpected keys of a container mapping (values checked by the caller)."""
    return ([f"missing field '{k}'" for k in keys if k not in mapping]
            + [f"unexpected field '{k}'" for k in mapping if k not in keys])


def _validate_entries(name: str, entries: list) -> list[str]:
    errors = []
    first = entries[0].get("type") if isinstance(entries[0], dict) else None
    if first != "proposed":
        errors.append(f"{name}: the first entry must be 'proposed'")
    previous_date = None
    for number, entry in enumerate(entries, start=1):
        where = f"{name}: entry {number}"
        if not isinstance(entry, dict):
            errors.append(f"{where}: expected a mapping")
            continue
        type_ = entry.get("type")
        if type_ not in ENTRY_TYPES:
            errors.append(f"{where}: unknown entry type {type_!r} "
                          f"(expected one of {', '.join(ENTRY_TYPES)})")
            continue
        author, required, optional = ENTRY_TYPES[type_]
        where = f"{where} {type_}"
        errors += [f"{where}: {e}" for e in _check_fields(
            entry, (*COMMON_REQUIRED, *required), ("migrated", *optional))]
        if author and entry.get("by") in AUTHORS and entry["by"] != author:
            errors.append(f"{where}: must be by {author}")
        if type_ == "proposed" and number > 1 and first == "proposed":
            errors.append(f"{where}: 'proposed' appears more than once")
        date = entry.get("date")
        if _is_date(date):
            if previous_date is not None and date < previous_date:
                errors.append(f"{where}: date {date} is before the previous entry "
                              f"({previous_date})")
            previous_date = date
    return errors


def _validate_thread(name: str, data) -> list[str]:
    if not isinstance(data, dict):
        return [f"{name}: expected a mapping with 'id' and 'entries'"]
    errors = [f"{name}: {e}" for e in _check_keys(data, THREAD_KEYS)]
    req_id = data.get("id")
    if "id" in data and (not isinstance(req_id, str) or not ID_RE.fullmatch(req_id)):
        errors.append(f"{name}: id {req_id!r} is not of the form REQ-<n>")
    elif "id" in data and name != f"{req_id}.yaml":
        errors.append(f"{name}: file name does not match id {req_id}")
    entries = data.get("entries")
    if "entries" in data:
        if isinstance(entries, list) and entries:
            errors += _validate_entries(name, entries)
        else:
            errors.append(f"{name}: entries must be a non-empty list")
    return errors


def _validate_deliveries(name: str, data) -> list[str]:
    if not isinstance(data, dict) or not isinstance(data.get("deliveries"), list):
        return [f"{name}: expected a mapping with a 'deliveries' list"]
    errors = [f"{name}: {e}" for e in _check_keys(data, DELIVERIES_KEYS)]
    previous_date = None
    for number, meeting in enumerate(data["deliveries"], start=1):
        where = f"{name}: meeting {number}"
        if not isinstance(meeting, dict):
            errors.append(f"{where}: expected a mapping")
            continue
        notes = meeting.get("thread")
        errors += [f"{where}: {e}" for e in _check_fields(
            {k: v for k, v in meeting.items() if k != "thread"}, ("date", "theme"), ())]
        date = meeting.get("date")
        if _is_date(date):
            if previous_date is not None and date <= previous_date:
                errors.append(f"{where}: date {date} is not after the previous meeting")
            previous_date = date
        if not isinstance(notes, list):
            errors.append(f"{where}: thread must be a list (possibly empty)")
            continue
        for index, note in enumerate(notes, start=1):
            if not isinstance(note, dict):
                errors.append(f"{where} note {index}: expected a mapping")
                continue
            errors += [f"{where} note {index}: {e}" for e in _check_fields(
                note, ("date", "by", "text"), ("channel", "migrated"))]
    return errors


def validate(folder: Path) -> list[str]:
    """Return a list of human-readable errors for the `quality/` folder."""
    errors: list[str] = []
    if not (folder / DELIVERIES_FILE).exists():
        errors.append(f"{DELIVERIES_FILE}: missing")
    seen_ids: dict[str, str] = {}
    for path in _yaml_files(folder):
        text = _read(path)
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            errors.append(f"{path.name}: not valid YAML ({exc})")
            continue
        if path.name == DELIVERIES_FILE:
            errors += _validate_deliveries(path.name, data)
        else:
            errors += _validate_thread(path.name, data)
            req_id = data.get("id") if isinstance(data, dict) else None
            if isinstance(req_id, str):
                if req_id in seen_ids:
                    errors.append(f"{path.name}: duplicate id {req_id} "
                                  f"(already used by {seen_ids[req_id]})")
                seen_ids.setdefault(req_id, path.name)
        if _canonical_text(path, data) != text:
            errors.append(f"{path.name}: not in canonical format "
                          "(run scripts/quality/regenerate.py to rewrite it)")
    return errors


# --- Replay ------------------------------------------------------------------


@dataclass(frozen=True)
class Requirement:
    """The current state of one requirement, replayed from its thread."""

    id: str
    spec: dict
    client_status: str
    latest_result: str
    latest_verification: dict | None
    open: bool
    current: bool

    @property
    def thread_path(self) -> str:
        """Path of the thread relative to the `quality/` folder (for links)."""
        return f"{REQUIREMENTS_DIR}/{self.id}.yaml"


def _replay_thread(data: dict) -> Requirement:
    spec: dict = {}
    status = "awaiting client"
    latest_verification = None
    for entry in data["entries"]:
        type_ = entry["type"]
        if type_ == "proposed":
            spec = {k: entry[k] for k in REQUIREMENT_FIELDS}
        elif type_ in ("accepted", "rejected"):
            status = type_
        elif type_ == "signed-off":
            status = f"signed off {entry['result']}"
        elif type_ == "verified":
            latest_verification = entry
    open_ = status not in ("signed off ✅", "rejected")
    return Requirement(
        id=data["id"],
        spec=spec,
        client_status=status,
        latest_result=latest_verification["result"] if latest_verification else "⏳",
        latest_verification=latest_verification,
        open=open_,
        current=open_ or (spec["recurring"] and status == "signed off ✅"),
    )


def replay(folder: Path) -> list[Requirement]:
    """Replay every thread of a valid `quality/` folder, in ID order."""
    requirements = [_replay_thread(yaml.safe_load(_read(path)))
                    for path in sorted((folder / REQUIREMENTS_DIR).glob("*.yaml"))]
    return sorted(requirements, key=lambda r: int(r.id.split("-")[1]))


# --- Rendering ---------------------------------------------------------------

CURRENT_FILE = "CURRENT.md"
OVERVIEW_FILE = "OVERVIEW.md"

_GENERATED = (
    "> **Generated, do not edit.** Rebuilt from the threads in `requirements/` by "
    "`python scripts/quality/regenerate.py`. To change it, record an entry in a thread "
    "and regenerate (see [README.md](README.md))."
)

_GRID = """\
| Grid | What it asks | Where it is shown |
|---|---|---|
| **Q1** | You questioned and specified the quality requirements of your product | Each requirement below: statement, characteristic, metric & threshold, why. Its thread shows what the team proposed and what the client accepted, amended or rejected. |
| **Q2** | You defined how you'll know each requirement is met | *Verification*, *When* and *Owner* of each requirement below |
| **Q3** | You actually ran those checks | *Latest result* and its evidence below; every `verified` entry, with its evidence and raw output, in the threads |"""


def _cell(value) -> str:
    return " ".join(str(value).split()).replace("|", r"\|")


def _link(req: Requirement) -> str:
    return f"[{req.thread_path}]({req.thread_path})"


def _render_requirement(req: Requirement) -> str:
    spec = req.spec
    lines = [
        f"## {req.id} · {spec['title']}",
        "",
        spec["statement"].strip(),
        "",
        f"- **Characteristic:** {spec['characteristic']}",
        f"- **Metric & threshold:** {_cell(spec['metric'])}",
        f"- **Why (client need):** {_cell(spec['why'])}",
        f"- **Verification:** {_cell(spec['verification'])}",
        f"- **When:** {_cell(spec['when'])}",
        f"- **Owner:** {_cell(spec['owner'])}",
        f"- **Delivery:** {spec['delivery']}",
        f"- **Recurring:** {'yes' if spec['recurring'] else 'no'}",
        f"- **Client status:** {req.client_status}",
    ]
    verification = req.latest_verification
    if verification is None:
        lines.append("- **Latest result:** ⏳ not verified yet")
    else:
        lines += [
            f"- **Latest result:** {verification['result']} ({verification['date']})",
            "",
            "Evidence:",
            "",
            verification["evidence"].strip(),
        ]
        if "output" in verification:
            lines += ["", "```text", verification["output"].rstrip("\n"), "```"]
    lines += ["", f"Thread: {_link(req)}"]
    return "\n".join(lines)


def render_current(requirements: list[Requirement]) -> str:
    """Text of CURRENT.md: the Q1–Q3 grid, then every current requirement in full."""
    current = [r for r in requirements if r.current]
    parts = [
        "# Current quality requirements",
        _GENERATED,
        "What the team must reach now: every open requirement (not signed off ✅, not "
        "rejected), plus every recurring one with its latest result. Every requirement that "
        "ever existed is listed in [OVERVIEW.md](OVERVIEW.md).",
        _GRID,
        *([_render_requirement(r) for r in current] or ["No current requirement."]),
    ]
    return "\n\n".join(parts) + "\n"


def render_overview(requirements: list[Requirement]) -> str:
    """Text of OVERVIEW.md: one line per requirement, with a link to its thread."""
    rows = [
        f"| {r.id} | {_cell(r.spec['title'])} | {r.spec['delivery']} | {r.client_status} "
        f"| {r.latest_result} | {_link(r)} |"
        for r in requirements
    ]
    table = "\n".join([
        "| ID | Title | Delivery | Client status | Latest result | Thread |",
        "|---|---|---|---|---|---|",
        *rows,
    ])
    parts = [
        "# All quality requirements",
        _GENERATED,
        "One line per requirement that ever existed. What must be reached now is in "
        "[CURRENT.md](CURRENT.md).",
        table,
    ]
    return "\n\n".join(parts) + "\n"


# --- Regeneration ------------------------------------------------------------


def regenerate(folder: Path) -> list[str]:
    """Canonicalise, validate, then write CURRENT.md and OVERVIEW.md.

    Returns the validation errors; the views are only written when there are none.
    """
    canonicalise(folder)
    errors = validate(folder)
    if errors:
        return errors
    requirements = replay(folder)
    _write(folder / CURRENT_FILE, render_current(requirements))
    _write(folder / OVERVIEW_FILE, render_overview(requirements))
    return []
