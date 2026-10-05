"""Graine aléatoire globale, pour que les expériences soient reproductibles."""

from __future__ import annotations

import os
import random


def set_seed(seed: int) -> None:
    """Fixe la graine de ``random``, ``numpy`` et, s'il est installé, ``torch``."""
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:  # pragma: no cover
        pass
    try:  # torch est optionnel (extra `dl`)
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():  # pragma: no cover - dépend du matériel
            torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass
