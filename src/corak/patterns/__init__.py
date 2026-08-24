"""Built-in patterns.

Importing a pattern module registers it, so this is the only place that needs
touching when one is added.
"""

from __future__ import annotations

from .base import REGISTRY, pattern  # noqa: F401
from . import hexagons, scatter, triangles, waves  # noqa: F401


def names() -> list[str]:
    return sorted(REGISTRY)
