"""A grid of split rectangles -- the low-poly look."""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainter, QPen, QPolygonF

from ..noise import field
from .base import pattern


@pattern("triangles")
def draw(painter: QPainter, w: int, h: int, rng, pal) -> None:
    cols = rng.randint(10, 22)
    rows = max(3, round(cols * h / w))
    cw, ch = w / cols, h / rows
    f = field(rng)

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
                t = f(cx * 6.0, cy * 6.0) + rng.uniform(-0.05, 0.05)
                color = pal.ramp(t)
                painter.setBrush(color)
                # Antialiased neighbours would otherwise show a hairline of
                # background along every shared edge; stroking in the fill
                # colour overlaps the seam closed.
                painter.setPen(QPen(color, 1.0))
                painter.drawPolygon(QPolygonF([QPointF(*p) for p in tri]))
