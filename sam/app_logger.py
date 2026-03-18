"""
Petit utilitaire de logs (dev/prod).

Objectif :
- Remplacer les `print()` dispersés.
- Permettre d'activer/désactiver le niveau de détail via env.
"""

from __future__ import annotations

import logging
import os
from typing import Final


def _get_level() -> int:
    # Par défaut on limite le bruit en prod.
    level_str: str = os.getenv("MOSAM_LOG_LEVEL", "WARNING").upper()
    return getattr(logging, level_str, logging.INFO)


_DEFAULT_FORMAT: Final[str] = (
    "%(asctime)sZ %(levelname)s %(name)s - %(message)s"
)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(_DEFAULT_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False
    logger.setLevel(_get_level())
    return logger

