"""Local tool for reading the quality ledger: requirements table, threads, meetings.

Serves one HTML page (tool.html, next to this script) and a read-only JSON API
that only calls guess_arc.quality.ledger. Never writes, never runs git.

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
