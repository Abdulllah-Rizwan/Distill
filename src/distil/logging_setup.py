"""Logging configuration.

A single place to configure application logging. Deliberately never logs secrets or full user
content (Principle V) — call sites log identifiers and sizes, not note text or API keys.
"""

from __future__ import annotations

import logging

_CONFIGURED = False


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logging once (idempotent)."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
    )
    _CONFIGURED = True
