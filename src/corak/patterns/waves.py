"""Stacked sine bands."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainter, QPolygonF

from ..frame import Frame
from .base import pattern


@pattern("waves")
def draw(painter: QPainter, frame: Frame, rng, pal) -> None:
    w, h = frame.width, frame.height
    band = frame.mm(rng.uniform(22.0, 70.0))
    bands = max(3, round(h / band))
    steps = max(64, w // 12)
    amp = band * rng.uniform(0.35, 1.1)
    freq = rng.uniform(0.6, 2.2)
    drift = rng.uniform(-0.5, 0.5)

    painter.setPen(Qt.PenStyle.NoPen)
    hue_base = pal.colour_rng().random()
    painter.fillRect(0, 0, w, h, pal.shade(hue_base, 0.0))

    # Painted back to front as filled regions down to the bottom edge, so the
    # bands overlap rather than leaving gaps where the curves diverge.
    for i in range(bands):
        base = h * (i + 1) / (bands + 1)
        phase = rng.uniform(0, math.tau)
        local_amp = amp * (0.4 + 0.6 * (i / max(1, bands - 1)))
        curve = []
        for s in range(steps + 1):
            x = w * s / steps
            u = x / w
            y = base + local_amp * math.sin(u * math.tau * freq + phase) * (1.0 + drift * u)
            curve.append(QPointF(x, y))
        # Bands walk the lightness ramp while the hue barely moves, so a
        # multi-hue scheme grades rather than striping in unrelated colours.
        painter.setBrush(pal.shade(hue_base + 0.25 * (i / bands), (i + 1) / bands))
        painter.drawPolygon(
            QPolygonF(curve + [QPointF(float(w), float(h)), QPointF(0.0, float(h))])
        )
