"""Configuration du logging, volontairement minimale."""

from __future__ import annotations

import logging

_DEFAULT_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_configured = False


def setup_logging(level: int | str = logging.INFO) -> None:
    """Installe un handler console unique. Idempotent."""
    global _configured
    if _configured:
        logging.getLogger("ncp").setLevel(level)
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT, datefmt="%H:%M:%S"))
    root = logging.getLogger("ncp")
    root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Logger préfixé ``ncp.`` pour que ``setup_logging`` le pilote."""
    suffix = name.removeprefix("ncp.").removeprefix("ncp")
    return logging.getLogger(f"ncp.{suffix}" if suffix else "ncp")
