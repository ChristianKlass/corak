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
from .themes import Theme, get as get_theme

SEED_MAX = 1 << 24


class UnknownPattern(KeyError):
    pass


class NoPatternsEnabled(RuntimeError):
    pass


class Engine:
    def __init__(
        self,
        enabled: Iterable[str] | None = None,
        themes: Sequence[Theme] = (),
    ) -> None:
        self.enabled: list[str] = list(enabled) if enabled is not None else names()
        # User-derived themes, which `get` does not know about on its own.
        self.themes: Sequence[Theme] = tuple(themes)

    def theme_for(self, design: Design) -> Theme:
        return get_theme(design.theme, self.themes)

    def available(self) -> Sequence[str]:
        return names()

    def new_design(
        self,
        rng: random.Random,
        pattern: str | None = None,
        palette_seed: int | None = None,
        theme: Theme | str | None = None,
    ) -> Design:
        """Build a design, optionally holding the pattern or the palette fixed."""
        resolved = theme if isinstance(theme, Theme) else get_theme(theme or "", self.themes)
        if theme is None:
            theme_id = ""
        else:
            theme_id = resolved.id

        if pattern is None:
            choices = [p for p in self.enabled if p in REGISTRY]
            if theme is not None and resolved.patterns:
                # A theme's pattern list narrows what is enabled rather than
                # replacing it, so disabling a pattern still means disabled.
                narrowed = [p for p in choices if p in resolved.patterns]
                choices = narrowed or choices
            if not choices:
                raise NoPatternsEnabled("no enabled pattern is available")
            pattern = rng.choice(choices)
        elif pattern not in REGISTRY:
            raise UnknownPattern(pattern)
        return Design(
            pattern=pattern,
            pattern_seed=rng.randrange(SEED_MAX),
            palette_seed=rng.randrange(SEED_MAX) if palette_seed is None else palette_seed,
            theme=theme_id,
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
        theme = self.theme_for(design) if design.theme else None
        # The quiet mode works poorly against a light ground, so on an
        # unconstrained palette it forces a dark one. A theme that states which
        # it wants overrides that: otherwise its background would go dark while
        # its shapes stayed light.
        undecided = theme is None or theme.dark is None
        forced_dark = True if (effects.get("calm") and undecided) else None
        palette = (
            Palette.for_theme(design.palette_seed, theme, dark=forced_dark)
            if theme is not None
            else Palette(design.palette_seed, dark=forced_dark)
        )
        image = QImage(width, height, QImage.Format.Format_RGB32)
        image.fill(palette.background)

        painter = QPainter(image)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            frame = Frame(
                width,
                height,
                px_per_mm or Frame(width, height).px_per_mm,
                theme.scale if theme is not None else 1.0,
                theme.depth if theme is not None else 1.0,
            )
            draw(painter, frame, random.Random(design.pattern_seed), palette)
        finally:
            painter.end()

        if effects:
            # Seeded from the design so grain is part of the reproducible image
            # rather than something that changes on every redraw.
            fx.apply_all(
                image,
                effects,
                random.Random(design.pattern_seed ^ 0x5F5E1),
                # A theme that supplies its own colours has already chosen how
                # saturated it wants to be.
                desaturate_by=0.25 if (theme is not None and theme.colors) else 1.0,
            )
        return image
