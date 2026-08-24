"""Stacked sine bands."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainter, QPolygonF

from .base import pattern


@pattern("waves")
def draw(painter: QPainter, w: int, h: int, rng, pal) -> None:
    bands = rng.randint(5, 14)
    steps = max(64, w // 12)
    amp = h / bands * rng.uniform(0.35, 1.1)
    freq = rng.uniform(0.6, 2.2)
    drift = rng.uniform(-0.5, 0.5)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.fillRect(0, 0, w, h, pal.ramp(0.0))

    # Painted back to front as filled regions down to the bottom edge, so the
    # bands overlap rather than leaving gaps where the curves diverge.
    for i in range(bands):
        base = h * (i + 1) / (bands + 1)
        phase = rng.uniform(0, math.tau)
        local_amp = amp * (0.4 + 0.6 * (i / max(1, bands - 1)))
        points = [QPointF(0.0, float(h)), QPointF(float(w), float(h))]
        curve = []
        for s in range(steps + 1):
            x = w * s / steps
            u = x / w
            y = base + local_amp * math.sin(u * math.tau * freq + phase) * (
                1.0 + drift * u
            )
            curve.append(QPointF(x, y))
        painter.setBrush(pal.ramp((i + 1) / bands))
        painter.drawPolygon(QPolygonF(curve + [QPointF(float(w), float(h)), QPointF(0.0, float(h))]))
