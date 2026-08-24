"""Colour scheme generation.

Step 1 keeps this deliberately small: enough structure for the Left arrow
(recolour without changing the pattern) to be visible, with the interface the
richer scheme logic in step 2 will implement behind.
"""

from __future__ import annotations

import colorsys
import random

from PySide6.QtGui import QColor


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def hsl(h: float, s: float, ll: float) -> QColor:
    r, g, b = colorsys.hls_to_rgb(h % 1.0, _clamp(ll), _clamp(s))
    return QColor.fromRgbF(r, g, b)


class Palette:
    """An ordered colour ramp plus a background."""

    def __init__(self, seed: int, dark: bool | None = None) -> None:
        self.seed = seed
        rng = random.Random(seed)
        self.dark = rng.random() < 0.68 if dark is None else dark

        base = rng.random()
        spread = rng.choice((0.04, 0.08, 0.14, 0.33, 0.5))
        sat = rng.uniform(0.35, 0.72)

        self.colors = [
            hsl(
                base + spread * (i / 4.0) * rng.uniform(0.85, 1.15),
                sat * rng.uniform(0.8, 1.1),
                (0.30 + 0.42 * (i / 4.0)) if self.dark else (0.42 + 0.34 * (i / 4.0)),
            )
            for i in range(5)
        ]

        self.background = hsl(
            base + spread * 0.5,
            sat * 0.5,
            rng.uniform(0.06, 0.12) if self.dark else rng.uniform(0.88, 0.95),
        )

        # Traversing the whole ramp at once reads as muddy; most images look
        # better confined to a slice of it.
        width = rng.uniform(0.55, 1.0)
        self._t0 = rng.uniform(0.0, 1.0 - width)
        self._t1 = self._t0 + width

    def ramp(self, t: float, full: bool = False) -> QColor:
        """Sample the ramp. t is 0..1; `full` ignores the cohesion slice."""
        t = _clamp(t)
        if not full:
            t = self._t0 + (self._t1 - self._t0) * t
        pos = t * (len(self.colors) - 1)
        i = min(int(pos), len(self.colors) - 2)
        return blend(self.colors[i], self.colors[i + 1], pos - i)


def blend(a: QColor, b: QColor, t: float) -> QColor:
    t = _clamp(t)
    return QColor.fromRgbF(
        a.redF() + (b.redF() - a.redF()) * t,
        a.greenF() + (b.greenF() - a.greenF()) * t,
        a.blueF() + (b.blueF() - a.blueF()) * t,
    )
