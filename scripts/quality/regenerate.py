"""Validate the quality ledger, rewrite its YAML canonically and regenerate its views.

Rewrites hand-edited files of quality/ in canonical form, validates every thread
and deliveries.yaml, then regenerates quality/CURRENT.md and quality/OVERVIEW.md.
Exit code 0 when everything is valid, 1 otherwise (the views are then left as is).

    python scripts/quality/regenerate.py [--quality quality]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from guess_arc.paths import QUALITY_DIR
from guess_arc.quality import ledger


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quality", type=Path, default=QUALITY_DIR,
                        help="quality folder (default: quality/ at the repo root)")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    errors = ledger.regenerate(args.quality)
    for error in errors:
        print(error)
    if errors:
        print(f"{len(errors)} error(s): views not regenerated.")
        return 1
    print(f"OK: {ledger.CURRENT_FILE} and {ledger.OVERVIEW_FILE} regenerated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
