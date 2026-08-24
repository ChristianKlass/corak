"""Built-in patterns.

Importing a pattern module registers it, so this is the only place that needs
touching when one is added.
"""

from __future__ import annotations

from . import (  # noqa: F401
    bokeh,
    constellation,
    flowing,
    hexagons,
    scatter,
    triangles,
    waves,
)
from .base import REGISTRY, pattern  # noqa: F401


def names() -> list[str]:
    return sorted(REGISTRY)
