"""Colour scheme generation.

Schemes are built from hue relationships on the colour wheel rather than picked
at random, which is what keeps five colours looking like a set instead of five
unrelated choices.
"""

from __future__ import annotations

import colorsys
import random
from typing import Iterable, Sequence

from PySide6.QtGui import QColor

RAMP_STOPS = 5

# Hue offsets in turns, relative to the base hue. Weighted rather than uniform:
# the tight schemes read as deliberate at wallpaper scale, while triads applied
# across a whole screen tend to look like a test card.
SCHEMES: dict[str, Sequence[float]] = {
    "mono": (0.0,),
    "analogous": (-0.08, 0.0, 0.08),
    "complement": (0.0, 0.5),
    "split": (0.0, 0.42, 0.58),
    "triad": (0.0, 1 / 3, 2 / 3),
}
SCHEME_WEIGHTS = {
    "mono": 26,
    "analogous": 34,
    "complement": 16,
    "split": 14,
    "triad": 10,
}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def hsl(h: float, s: float, ll: float) -> QColor:
    r, g, b = colorsys.hls_to_rgb(h % 1.0, _clamp(ll), _clamp(s))
    return QColor.fromRgbF(r, g, b)


def blend(a: QColor, b: QColor, t: float) -> QColor:
    t = _clamp(t)
    return QColor.fromRgbF(
        a.redF() + (b.redF() - a.redF()) * t,
        a.greenF() + (b.greenF() - a.greenF()) * t,
        a.blueF() + (b.blueF() - a.blueF()) * t,
    )


class Palette:
    """An ordered colour ramp plus a background colour."""

    def __init__(
        self,
        seed: int,
        dark: bool | None = None,
        scheme: str | None = None,
    ) -> None:
        self.seed = seed
        rng = random.Random(seed)
        # The draw happens either way: consuming it only when `dark` is unset
        # would shift the rest of the stream, so forcing a dark palette would
        # silently change the hue and scheme too.
        roll = rng.random()
        self.dark = roll < 0.68 if dark is None else dark

        if scheme is None:
            scheme = rng.choices(
                list(SCHEME_WEIGHTS), weights=list(SCHEME_WEIGHTS.values())
            )[0]
        elif scheme not in SCHEMES:
            raise ValueError(f"unknown scheme: {scheme}")
        self.scheme = scheme

        self.base_hue = rng.random()
        offsets = SCHEMES[scheme]
        saturation = rng.uniform(0.32, 0.74)
        lo, hi = (0.26, 0.70) if self.dark else (0.40, 0.80)

        self.colors = []
        for i in range(RAMP_STOPS):
            t = i / (RAMP_STOPS - 1)
            # Walking the offsets in order rather than sampling them randomly
            # means the ramp moves through the scheme instead of jumping about.
            hue = self.base_hue + offsets[round(t * (len(offsets) - 1))]
            self.colors.append(
                hsl(
                    hue + rng.uniform(-0.012, 0.012),
                    saturation * rng.uniform(0.82, 1.12),
                    lo + (hi - lo) * t,
                )
            )

        self.background = hsl(
            self.base_hue + offsets[0],
            saturation * 0.5,
            rng.uniform(0.05, 0.11) if self.dark else rng.uniform(0.88, 0.95),
        )

        # Traversing the whole ramp in one image usually reads as muddy; most
        # look better confined to a slice of it.
        width = rng.uniform(0.55, 1.0)
        self._t0 = rng.uniform(0.0, 1.0 - width)
        self._t1 = self._t0 + width

    @classmethod
    def from_hex(cls, codes: Iterable[str], dark: bool | None = None) -> "Palette":
        """Build a palette from explicit hex codes, ordered dark to light."""
        colors = []
        for code in codes:
            color = QColor(code if code.startswith("#") else f"#{code}")
            if not color.isValid():
                raise ValueError(f"not a colour: {code}")
            colors.append(color)
        if not colors:
            raise ValueError("at least one colour is required")

        colors.sort(key=lambda c: c.lightnessF())
        palette = cls.__new__(cls)
        palette.seed = -1
        palette.scheme = "custom"
        palette.base_hue = colors[0].hueF() if colors[0].hueF() >= 0 else 0.0
        palette.colors = colors
        palette.dark = colors[len(colors) // 2].lightnessF() < 0.5 if dark is None else dark
        palette.background = (
            colors[0].darker(180) if palette.dark else colors[-1].lighter(140)
        )
        palette._t0, palette._t1 = 0.0, 1.0
        return palette

    def ramp(self, t: float, full: bool = False) -> QColor:
        """Sample the ramp. t is 0..1; `full` ignores the cohesion slice."""
        t = _clamp(t)
        if not full:
            t = self._t0 + (self._t1 - self._t0) * t
        if len(self.colors) == 1:
            return self.colors[0]
        pos = t * (len(self.colors) - 1)
        i = min(int(pos), len(self.colors) - 2)
        return blend(self.colors[i], self.colors[i + 1], pos - i)
