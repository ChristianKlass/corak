"""Pattern registry.

A pattern is a function that paints onto an already-cleared QPainter. It gets a
Frame, its own seeded RNG, and a palette -- nothing else, so patterns stay
independently testable. Feature sizes come from the frame in millimetres so the
same design keeps its apparent scale across displays of different densities.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QPainter

from ..frame import Frame
from ..palette import Palette

PatternFn = Callable[[QPainter, Frame, "object", Palette], None]

REGISTRY: dict[str, PatternFn] = {}


def pattern(name: str) -> Callable[[PatternFn], PatternFn]:
    def register(fn: PatternFn) -> PatternFn:
        REGISTRY[name] = fn
        return fn

    return register
