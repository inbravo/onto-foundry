"""
Shared logging configuration for ontology-foundry.

Usage:
    from _shared import logging_config
    logging_config.setup()
    log = logging.getLogger("ontology.module_name")
"""
# ─────────────────────────────────────────────────────
# Author   : Amit Dixit
# GitHub   : https://github.com/inbravo
# Web      : https://inbravo.github.io
# LinkedIn : https://www.linkedin.com/in/inbravo/
# ─────────────────────────────────────────────────────
from __future__ import annotations

import logging
import sys


# ── setup ─────────────────────────────────────────────────────────────────────

def setup(level: int = logging.INFO) -> None:
    logging.basicConfig(
        stream=sys.stdout,
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
