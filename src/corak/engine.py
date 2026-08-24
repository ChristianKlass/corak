"""Rendering.

Draws onto a QImage rather than a QPixmap: QImage has no GUI-thread affinity, so
the same engine backs the interactive window, a background thread, and the
headless CLI running under the offscreen platform plugin.
"""

from __future__ import annotations

import random
from typing import Iterable, Sequence

from PySide6.QtGui import QImage, QPainter

from .design import Design
from .palette import Palette
from .patterns import REGISTRY, names

SEED_MAX = 1 << 24


class UnknownPattern(KeyError):
    pass


class NoPatternsEnabled(RuntimeError):
    pass


class Engine:
    def __init__(self, enabled: Iterable[str] | None = None) -> None:
        self.enabled: list[str] = list(enabled) if enabled is not None else names()

    def available(self) -> Sequence[str]:
        return names()

    def new_design(
        self,
        rng: random.Random,
        pattern: str | None = None,
        palette_seed: int | None = None,
    ) -> Design:
        """Build a design, optionally holding the pattern or the palette fixed."""
        if pattern is None:
            choices = [p for p in self.enabled if p in REGISTRY]
            if not choices:
                raise NoPatternsEnabled("no enabled pattern is available")
            pattern = rng.choice(choices)
        elif pattern not in REGISTRY:
            raise UnknownPattern(pattern)
        return Design(
            pattern=pattern,
            pattern_seed=rng.randrange(SEED_MAX),
            palette_seed=rng.randrange(SEED_MAX) if palette_seed is None else palette_seed,
        )

    def render(self, design: Design, width: int, height: int) -> QImage:
        try:
            draw = REGISTRY[design.pattern]
        except KeyError as exc:
            raise UnknownPattern(design.pattern) from exc

        palette = Palette(design.palette_seed)
        image = QImage(width, height, QImage.Format.Format_RGB32)
        image.fill(palette.background)

        painter = QPainter(image)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            draw(painter, width, height, random.Random(design.pattern_seed), palette)
        finally:
            painter.end()
        return image
