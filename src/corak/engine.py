"""Rendering.

Draws onto a QImage rather than a QPixmap: QImage has no GUI-thread affinity, so
the same engine backs the interactive window, a background thread, and the
headless CLI running under the offscreen platform plugin.
"""

from __future__ import annotations

import random
from typing import Iterable, Mapping, Sequence

from PySide6.QtGui import QImage, QPainter

from . import effects as fx
from .design import Design
from .frame import Frame
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

    def render(
        self,
        design: Design,
        width: int,
        height: int,
        effects: Mapping[str, float] | None = None,
        px_per_mm: float | None = None,
    ) -> QImage:
        try:
            draw = REGISTRY[design.pattern]
        except KeyError as exc:
            raise UnknownPattern(design.pattern) from exc

        effects = dict(effects or {})
        # The quiet mode only works against a dark ground; letting it land on a
        # near-white palette produces a washed grey rather than a calm one.
        palette = Palette(design.palette_seed, dark=True if effects.get("calm") else None)
        image = QImage(width, height, QImage.Format.Format_RGB32)
        image.fill(palette.background)

        painter = QPainter(image)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            frame = Frame(width, height, px_per_mm) if px_per_mm else Frame(width, height)
            draw(painter, frame, random.Random(design.pattern_seed), palette)
        finally:
            painter.end()

        if effects:
            # Seeded from the design so grain is part of the reproducible image
            # rather than something that changes on every redraw.
            fx.apply_all(image, effects, random.Random(design.pattern_seed ^ 0x5F5E1))
        return image
