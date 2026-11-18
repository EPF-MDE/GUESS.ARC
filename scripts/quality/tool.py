"""Local tool for the quality ledger: read the threads and meetings, record new entries.

Serves one HTML page (tool.html, next to this script) and a small JSON API that
only calls guess_arc.quality.ledger. Writes are appends only (new entry, new
requirement, new meeting, new meeting note): nothing can edit or delete a past
entry. Each write regenerates CURRENT.md and OVERVIEW.md. Never runs git.

    python scripts/quality/tool.py [--quality quality] [--port 8765]

Then open the printed URL. Ctrl+C stops it.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from guess_arc.paths import QUALITY_DIR
from guess_arc.quality import ledger

PAGE = Path(__file__).with_name("tool.html")


def _api(folder: Path, path: str):
    """(status, payload) for one API path. The folder is validated on every call."""
    if path == "/api/vocabulary":
        # What the forms offer: the ledger's own lists, never a copy of them.
        return 200, {
            "fields": ledger.REQUIREMENT_FIELDS,
            "entry_types": {t: author for t, (author, _, _) in ledger.ENTRY_TYPES.items()},
            "spec_changes": ledger.SPEC_CHANGES,
            "characteristics": ledger.CHARACTERISTICS,
            "results": ledger.RESULTS,
            "authors": ledger.AUTHORS,
        }
    errors = ledger.validate(folder)
    if errors:
        return 409, {"errors": errors}
    if path == "/api/requirements":
        return 200, ledger.replay(folder)
    if path.startswith("/api/requirements/"):
        req_id = path.rsplit("/", 1)[1]
        try:
            return 200, ledger.read_thread(folder, req_id)
        except FileNotFoundError:
            return 404, {"errors": [f"unknown requirement {req_id}"]}
    if path == "/api/meetings":
        return 200, ledger.meetings(folder)
    return 404, {"errors": [f"unknown API path {path}"]}


def _append(folder: Path, path: str, body: dict):
    """(status, payload) for one write: always an append through the ledger module."""
    parts = path.strip("/").split("/")
    try:
        if parts == ["api", "requirements"]:
            return 201, {"id": ledger.create_requirement(folder, body)}
        if len(parts) == 4 and parts[:2] == ["api", "requirements"] and parts[3] == "entries":
            ledger.add_entry(folder, parts[2], body)
            return 201, {"id": parts[2]}
        if parts == ["api", "meetings"]:
            ledger.add_meeting(folder, body)
            return 201, {}
        if len(parts) == 4 and parts[:2] == ["api", "meetings"] and parts[3] == "notes":
            ledger.add_meeting_note(folder, parts[2], body)
            return 201, {}
    except ledger.AppendRefused as refused:
        return 422, {"errors": refused.errors}
    return 404, {"errors": [f"unknown API path {path}"]}


def _json(payload) -> bytes:
    def default(value):
        if dataclasses.is_dataclass(value):
            return dataclasses.asdict(value)
        return str(value)  # dates

    return json.dumps(payload, default=default, ensure_ascii=False).encode("utf-8")


def make_handler(folder: Path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                self._send(200, "text/html; charset=utf-8", PAGE.read_bytes())
            elif path.startswith("/api/"):
                status, payload = _api(folder, path)
                self._send(status, "application/json; charset=utf-8", _json(payload))
            else:
                self._send(404, "text/plain; charset=utf-8", b"Not found")

        def do_POST(self):
            # Only POST (append) exists: no PUT, PATCH or DELETE, so no past entry
            # can be edited or removed from the tool.
            if self.headers.get_content_type() != "application/json":
                # A JSON content type forces a CORS preflight, which this server never
                # answers: another web page open in the browser cannot write here.
                self._send(415, "application/json; charset=utf-8",
                           _json({"errors": ["expected Content-Type: application/json"]}))
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                body = None
            if not isinstance(body, dict):
                status, payload = 400, {"errors": ["the request body must be a JSON object"]}
            else:
                status, payload = _append(folder, self.path.split("?", 1)[0], body)
            self._send(status, "application/json; charset=utf-8", _json(payload))

        def _send(self, status: int, content_type: str, body: bytes):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass  # keep the terminal quiet while screen-sharing

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quality", type=Path, default=QUALITY_DIR,
                        help="quality folder (default: quality/ at the repo root)")
    parser.add_argument("--port", type=int, default=8765, help="local port (default: 8765)")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.quality))
    except OSError as exc:
        print(f"Cannot listen on port {args.port} ({exc}). Try --port <another>.")
        return 1
    print(f"Quality ledger: http://127.0.0.1:{server.server_port}/  (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
