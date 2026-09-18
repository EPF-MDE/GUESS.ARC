"""Force stdout/stderr en UTF-8, y compris sur la console Windows (cp1252 par
défaut), pour que les accents et le français s'affichent correctement.
"""

from __future__ import annotations

import sys


def ensure_utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
