"""A flat-top hexagonal tiling."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainter, QPainterPath, QPen, QPolygonF

from ..frame import Frame
from ..noise import field
from ..shading import drop_shadow, shape_brush, shift, underlay
from .base import pattern


def _corners(cx: float, cy: float, r: float) -> list[QPointF]:
    return [
        QPointF(cx + r * math.cos(math.pi / 3.0 * i), cy + r * math.sin(math.pi / 3.0 * i))
        for i in range(6)
    ]


@pattern("hexagons")
def draw(painter: QPainter, frame: Frame, rng, pal) -> None:
    w, h = frame.width, frame.height
    r = frame.mm(rng.uniform(14.0, 34.0))
    dx = r * 1.5
    dy = r * math.sqrt(3.0)
    # Two fields, deliberately at different scales. Hue drifts slowly across the
    # whole image while lightness varies shape to shape: driving both from one
    # field makes a small spatial step cross a hue boundary, and neighbouring
    # shapes jump from orange to blue.
    hue_field = field(pal.colour_rng(), terms=2, frequency=0.5)
    light_field = field(rng, frequency=2.2)
    depth = frame.depth

    underlay(painter, frame, pal, rng, depth)

    # One light direction for the whole image: shapes lit from different angles
    # read as a collage rather than a surface.
    light = rng.uniform(0, math.tau)
    lift = r * 0.07 * depth

    # A visible gap is a deliberate look; below that threshold the tiles are
    # meant to touch, and each is stroked in its own colour so antialiasing
    # cannot leave a hairline of background along the shared edges.
    # Thin: with shading doing the separating, a wide gap reads as heavy
    # leading between tiles rather than as depth.
    facet = rng.uniform(0.12, 0.26)
    gap = rng.uniform(0.0, 0.018)
    seamless = gap <= 0.006

    # One extra ring past each edge so no partial tile is missing at the border.
    for col in range(-1, int(w / dx) + 2):
        for row in range(-1, int(h / dy) + 2):
            cx = col * dx
            cy = row * dy + (dy / 2.0 if col % 2 else 0.0)
            hue_t = hue_field(cx / w, cy / h)
            light_t = light_field(cx / w, cy / h) + rng.uniform(-facet, facet)
            # The lightness field varies cell to cell, so it shades a colour
            # rather than choosing one: letting it pick would scatter a
            # multi-hue palette across neighbouring cells as noise.
            color = pal.shade(hue_t, light_t, from_light=0.12, relief=0.24)
            path = QPainterPath()
            path.addPolygon(QPolygonF(_corners(cx, cy, r)))
            path.closeSubpath()

            if lift > 0.0 and not seamless:
                drop_shadow(painter, path, light, lift, depth)
            painter.setBrush(
                shape_brush(color, QPointF(cx, cy), r, light, depth) if depth else color
            )
            painter.setPen(
                QPen(color, 1.0)
                if seamless
                else QPen(shift(pal.background, 0.10), r * gap * 2.0)
            )
            painter.drawPath(path)
