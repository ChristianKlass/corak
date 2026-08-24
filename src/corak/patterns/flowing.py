"""Large organic shapes, each with a lit edge.

The shapes are closed curves through jittered points rather than anything
regular, and every one carries a bright contour stroke. The stroke is doing most
of the work: without it the shapes merge into each other and the picture flattens
back into a gradient.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QLinearGradient, QPainter, QPen

from ..frame import Frame
from ..noise import field
from ..shading import cast_shadows, shift, smooth_loop, underlay
from .base import pattern


@pattern("flowing")
def draw(painter: QPainter, frame: Frame, rng, pal) -> None:
    w, h = frame.width, frame.height
    depth = frame.depth
    underlay(painter, frame, pal, rng, depth)

    colour_rng = pal.colour_rng()
    hue_field = field(colour_rng, terms=2, frequency=0.6)
    spread = colour_rng.choice((0.3, 0.6, 1.0))
    light = rng.uniform(0, math.tau)

    count = rng.randint(5, 11)
    # Deliberately large -- comparable to the frame. These are meant to run off
    # the edges rather than sit inside it.
    largest = min(w, h) * rng.uniform(0.30, 0.55)

    shapes = []
    for i in range(count):
        cx = rng.uniform(-0.15, 1.15) * w
        cy = rng.uniform(-0.15, 1.15) * h
        radius = largest * rng.uniform(0.35, 1.0)
        lobes = rng.randint(5, 9)
        wobble = rng.uniform(0.18, 0.5)
        start = rng.uniform(0, math.tau)
        points = [
            QPointF(
                cx + math.cos(start + math.tau * k / lobes) * radius * (1.0 + rng.uniform(-wobble, wobble)),
                cy + math.sin(start + math.tau * k / lobes) * radius * (1.0 + rng.uniform(-wobble, wobble)),
            )
            for k in range(lobes)
        ]
        hue_t = hue_field(min(1.0, max(0.0, cx / w)), min(1.0, max(0.0, cy / h)))
        hue_t += colour_rng.uniform(-spread, spread)
        shapes.append((smooth_loop(points, rng.uniform(0.4, 0.75)), pal.pick(hue_t), radius, cx, cy))

    stroke_width = max(1.0, frame.mm(rng.uniform(0.3, 0.9)))
    for path, color, radius, cx, cy in shapes:
        cast_shadows(
            painter, frame, [(path, radius * 0.05)], light, depth * 0.8,
            divisor=4, color=shift(pal.background, -0.25),
        )
        fill = QLinearGradient(cx - radius, cy - radius, cx + radius, cy + radius)
        fill.setColorAt(0.0, shift(color, 0.045 * depth))
        fill.setColorAt(1.0, shift(color, -0.055 * depth))
        painter.setBrush(fill)
        # A lighter version of the shape's own colour, not white: the edge is
        # the shape catching the light, not a line drawn around it.
        painter.setPen(QPen(shift(color, 0.18), stroke_width))
        painter.drawPath(path)
