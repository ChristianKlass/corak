"""A grid of split rectangles -- the low-poly look."""

from __future__ import annotations

from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainter, QPen, QPolygonF

from ..frame import Frame
from ..noise import field
from .base import pattern


@pattern("triangles")
def draw(painter: QPainter, frame: Frame, rng, pal) -> None:
    w, h = frame.width, frame.height
    cell = frame.mm(rng.uniform(26.0, 60.0))
    cols = max(3, round(w / cell))
    rows = max(3, round(h / cell))
    cw, ch = w / cols, h / rows
    # Hue drifts across the image; lightness varies cell to cell. See hexagons.
    hue_field = field(pal.colour_rng(), terms=2, frequency=0.5)
    light_field = field(rng, frequency=2.2)

    # Jitter keeps the grid from reading as graph paper, but a shared corner
    # must move as a single point or the triangles pull apart at the seams.
    jitter = rng.uniform(0.0, 0.28)
    corners = [
        [
            (
                x * cw + (rng.uniform(-jitter, jitter) * cw if 0 < x < cols else 0.0),
                y * ch + (rng.uniform(-jitter, jitter) * ch if 0 < y < rows else 0.0),
            )
            for x in range(cols + 1)
        ]
        for y in range(rows + 1)
    ]

    for y in range(rows):
        for x in range(cols):
            tl, tr = corners[y][x], corners[y][x + 1]
            bl, br = corners[y + 1][x], corners[y + 1][x + 1]
            flip = (x + y) % 2 == 0
            halves = ((tl, tr, br), (tl, br, bl)) if flip else ((tl, tr, bl), (tr, br, bl))
            for tri in halves:
                cx = sum(p[0] for p in tri) / 3.0 / w
                cy = sum(p[1] for p in tri) / 3.0 / h
                hue_t = hue_field(cx, cy)
                light_t = light_field(cx, cy) + rng.uniform(-0.04, 0.04)
                    # The lightness field varies cell to cell, so it shades a colour
                # rather than choosing one: letting it pick would scatter a
                # multi-hue palette across neighbouring cells as noise.
                color = pal.shade(hue_t, light_t, from_light=0.12)
                painter.setBrush(color)
                # Antialiased neighbours would otherwise show a hairline of
                # background along every shared edge; stroking in the fill
                # colour overlaps the seam closed.
                painter.setPen(QPen(color, 1.0))
                painter.drawPolygon(QPolygonF([QPointF(*p) for p in tri]))
