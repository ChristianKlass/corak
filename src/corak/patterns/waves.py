"""Stacked bands with a soft horizon."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QLinearGradient, QPainter, QPainterPath, QPolygonF

from ..frame import Frame
from ..noise import field
from ..shading import cast_shadows, shift, underlay
from .base import pattern


@pattern("waves")
def draw(painter: QPainter, frame: Frame, rng, pal) -> None:
    w, h = frame.width, frame.height
    depth = frame.depth
    underlay(painter, frame, pal, rng, depth)

    band = frame.mm(rng.uniform(22.0, 70.0))
    bands = max(3, round(h / band))
    steps = max(64, w // 12)
    amp = band * rng.uniform(0.35, 1.1)
    freq = rng.uniform(0.6, 2.2)
    drift = rng.uniform(-0.5, 0.5)

    colour_rng = pal.colour_rng()
    hue_field = field(colour_rng, terms=2, frequency=0.5)
    hue_base = colour_rng.random()
    # Each band leans a different way across the palette, so a set of distinct
    # hues shows as more than one of them.
    hue_span = colour_rng.uniform(0.25, 0.9)

    painter.setPen(Qt.PenStyle.NoPen)
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
        shape = QPolygonF(curve + [QPointF(float(w), float(h)), QPointF(0.0, float(h))])

        along = (i + 1) / bands
        color = pal.shade(hue_base + hue_span * along, along, relief=0.16)

        if depth > 0.0:
            # The band in front throws a shadow onto the one behind, which is
            # what separates stacked bands from a flat gradient.
            path = QPainterPath()
            path.addPolygon(shape)
            cast_shadows(
                painter, frame, [(path, band * 0.16)], math.pi / 2, depth * 0.7,
                divisor=4, color=shift(pal.background, -0.22),
            )
            # Lit along the length rather than across it, so a band reads as a
            # curved surface instead of a flat cut-out.
            lit = QLinearGradient(0.0, base - local_amp, 0.0, base + band)
            lit.setColorAt(0.0, shift(color, 0.05 * depth))
            lit.setColorAt(1.0, shift(color, -0.05 * depth))
            painter.setBrush(lit)
        else:
            painter.setBrush(color)
        painter.drawPolygon(shape)
