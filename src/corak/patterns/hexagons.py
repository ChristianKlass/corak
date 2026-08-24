"""A flat-top hexagonal tiling."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainter, QPen, QPolygonF

from ..frame import Frame
from ..noise import field
from .base import pattern


def _hexagon(cx: float, cy: float, r: float) -> QPolygonF:
    return QPolygonF(
        [
            QPointF(cx + r * math.cos(math.pi / 3.0 * i), cy + r * math.sin(math.pi / 3.0 * i))
            for i in range(6)
        ]
    )


@pattern("hexagons")
def draw(painter: QPainter, frame: Frame, rng, pal) -> None:
    w, h = frame.width, frame.height
    r = frame.mm(rng.uniform(9.0, 26.0))
    dx = r * 1.5
    dy = r * math.sqrt(3.0)
    f = field(rng)

    # A visible gap is a deliberate look; below that threshold the tiles are
    # meant to touch, and each is stroked in its own colour so antialiasing
    # cannot leave a hairline of background along the shared edges.
    gap = rng.uniform(0.0, 0.045)
    seamless = gap <= 0.02

    # One extra ring past each edge so no partial tile is missing at the border.
    for col in range(-1, int(w / dx) + 2):
        for row in range(-1, int(h / dy) + 2):
            cx = col * dx
            cy = row * dy + (dy / 2.0 if col % 2 else 0.0)
            t = f(cx / w * 6.0, cy / h * 6.0) + rng.uniform(-0.06, 0.06)
            color = pal.ramp(t)
            painter.setBrush(color)
            painter.setPen(
                QPen(color, 1.0) if seamless else QPen(pal.background, r * gap * 2.0)
            )
            painter.drawPolygon(_hexagon(cx, cy, r))
