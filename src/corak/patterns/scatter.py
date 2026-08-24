"""Loose shapes over open ground.

A lattice fills every pixel and reads as texture. What makes a wallpaper look
composed instead is the opposite: a handful of large shapes, more small ones,
clustered somewhere and absent elsewhere, with the background left visible
between them.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainter, QPen

from ..frame import Frame
from ..noise import field
from ..shading import capsule, drop_shadow, shape_brush, shift, underlay
from .base import pattern

# Rejected candidates are cheap and keeping the loop bounded matters more than
# hitting the target count exactly.
MAX_ATTEMPTS = 60


@pattern("scatter")
def draw(painter: QPainter, frame: Frame, rng, pal) -> None:
    w, h = frame.width, frame.height
    depth = frame.depth
    underlay(painter, frame, pal, rng, depth)

    hue_field = field(rng, terms=2)
    density = field(rng, terms=2)
    light = rng.uniform(0, math.tau)

    count = rng.randint(14, 34)
    largest = frame.mm(rng.uniform(55.0, 130.0))
    smallest = largest * rng.uniform(0.10, 0.22)
    # How sharply the sizes fall away. A high bias gives a few large shapes and
    # a tail of small ones, which is the hierarchy that reads as designed; a
    # flat distribution just looks like scattered confetti of one size.
    bias = rng.uniform(1.6, 3.2)
    threshold = rng.uniform(0.42, 0.66)
    stroke = rng.random() < 0.45
    # Large, well-separated shapes can carry real hue differences -- it was
    # small adjacent cells that turned a multi-hue scheme into confetti. Some
    # scatters take the whole scheme, others stay close to one hue.
    spread = rng.choice((0.05, 0.15, 0.45, 0.8))

    shapes = []
    for _ in range(count):
        for _attempt in range(MAX_ATTEMPTS):
            x, y = rng.uniform(0, w), rng.uniform(0, h)
            # Clustered rather than uniform: shapes gather where the density
            # field is high and leave the rest of the frame open.
            if density(x / w * 2.2, y / h * 2.2) > threshold:
                break
        else:
            continue
        t = rng.random() ** bias
        size = smallest + (largest - smallest) * t
        shapes.append((size, x, y, t))

    # Largest first, so the small shapes sit in front and the shadows stack the
    # right way round.
    shapes.sort(reverse=True)

    for size, x, y, t in shapes:
        aspect = rng.choice((1.0, 1.0, rng.uniform(1.4, 3.4)))
        width, height = size * aspect, size
        radius = size * rng.uniform(0.35, 0.5)
        angle = rng.uniform(0, math.tau)
        path = capsule(x, y, width, height, radius, angle)

        # Bigger shapes read as nearer, so they cast further.
        drop_shadow(painter, path, light, size * 0.10 * depth, depth)

        hue_t = hue_field(x / w * 1.3, y / h * 1.3) + rng.uniform(-spread, spread)
        color = pal.shade(hue_t, 0.25 + 0.7 * (1.0 - t) + rng.uniform(-0.08, 0.08))
        painter.setBrush(
            shape_brush(color, QPointF(x, y), size, light, depth) if depth else color
        )
        painter.setPen(
            QPen(shift(color, 0.12), max(1.0, size * 0.008)) if stroke else QPen(color, 1.0)
        )
        painter.drawPath(path)
