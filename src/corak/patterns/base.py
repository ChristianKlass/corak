"""Pattern registry.

A pattern is a function that paints onto an already-cleared QPainter.  It gets
the target size, its own seeded RNG, and a palette -- nothing else, so patterns
stay independently testable.
"""

from __future__ import annotations

from typing import Callable, Dict

from PySide6.QtGui import QPainter

from ..palette import Palette

PatternFn = Callable[[QPainter, int, int, "object", Palette], None]

REGISTRY: Dict[str, PatternFn] = {}


def pattern(name: str) -> Callable[[PatternFn], PatternFn]:
    def register(fn: PatternFn) -> PatternFn:
        REGISTRY[name] = fn
        return fn

    return register
