"""Circles thrown out of focus.

Almost nothing is sharp. The image is carried by overlapping translucent discs
at several depths, with a scatter of fine rings drawn over the top -- the rings
are what stop it reading as a blur of the background rather than as light.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen

from ..frame import Frame
from ..noise import field
from ..palette import oklch, to_oklch
from ..shading import shift, underlay
from .base import pattern

# Far to near, and blurred far harder than the scattered pattern: here the
# softness is the subject rather than a depth cue.
BANDS = ((0.00, 0.40, 14), (0.40, 0.75, 6), (0.75, 1.01, 2))


@pattern("bokeh")
def draw(painter: QPainter, frame: Frame, rng, pal) -> None:
    w, h = frame.width, frame.height
    depth = frame.depth
    underlay(painter, frame, pal, rng, depth)

    colour_rng = pal.colour_rng()
    hue_field = field(colour_rng, terms=2, frequency=0.7)
    density = field(rng, terms=2, frequency=0.8)

    count = rng.randint(40, 90)
    largest = frame.mm(rng.uniform(30.0, 80.0))
    smallest = largest * rng.uniform(0.08, 0.18)
    bias = rng.uniform(1.3, 2.4)
    threshold = rng.uniform(0.25, 0.5)
    spread = colour_rng.choice((0.3, 0.6, 1.0))
    # Translucent enough that overlaps mix rather than occlude, which is where
    # the colours in the middle of a cluster come from.
    alpha = colour_rng.uniform(0.32, 0.62)
    # Out-of-focus highlights are light, not pigment. Laid over a dark ground as
    # translucent paint a disc can only darken toward the background, which is
    # why this pattern came out dim on every dark theme; added instead, the
    # discs sit above the ground and overlaps brighten.
    lift = colour_rng.uniform(0.5, 0.75)
    accent_odds = colour_rng.choice((0.05, 0.12, 0.22))

    discs = []
    for _ in range(count):
        x, y = rng.uniform(-0.05, 1.05), rng.uniform(-0.05, 1.05)
        if density(min(1.0, max(0.0, x)), min(1.0, max(0.0, y))) < threshold:
            continue
        z = rng.random()
        radius = (smallest + (largest - smallest) * (z ** bias)) * rng.uniform(0.7, 1.3)
        discs.append((z, x * w, y * h, radius))
    discs.sort()

    for low, high, divisor in BANDS:
        band = [d for d in discs if low <= d[0] < high]
        if not band:
            continue
        if divisor <= 1 or depth <= 0.0:
            _discs(painter, band, frame, pal, rng, colour_rng, hue_field, spread, alpha,
                   accent_odds, lift)
            continue
        layer = QImage(
            max(1, w // divisor), max(1, h // divisor), QImage.Format.Format_ARGB32_Premultiplied
        )
        layer.fill(Qt.GlobalColor.transparent)
        into = QPainter(layer)
        try:
            into.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            into.scale(1.0 / divisor, 1.0 / divisor)
            _discs(into, band, frame, pal, rng, colour_rng, hue_field, spread, alpha,
                   accent_odds, lift)
        finally:
            into.end()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawImage(QRect(0, 0, w, h), layer)

    _rings(painter, frame, pal, rng, colour_rng, depth)


def _discs(painter, band, frame, pal, rng, colour_rng, hue_field, spread, alpha,
           accent_odds=0.0, lift=0.7) -> None:
    w, h = frame.width, frame.height
    painter.save()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
    for z, x, y, radius in band:
        hue_t = hue_field(min(1.0, max(0.0, x / w)), min(1.0, max(0.0, y / h)))
        hue_t += colour_rng.uniform(-spread, spread)
        color = pal.accent() if colour_rng.random() < accent_odds else pal.vivid(hue_t)

        # Raised to a floor rather than by a step: a dark palette entry
        # brightened by a step is still dark, and there is nothing to add.
        lightness, chroma, hue = to_oklch(color)
        # Chroma raised along with lightness. Adding light pushes every channel
        # toward white, so a disc that keeps its original chroma while getting
        # brighter comes out grey -- and a pile of them comes out white.
        # A floor, not an addition. Adding to a colour that is already light
        # lands at a lightness of 1, where the gamut holds no chroma at all --
        # the highlight was being forced to white by construction.
        lit = oklch(min(0.86, max(lift, lightness)), chroma * 1.5, hue)

        # Nearer discs carry more light; the far ones fall back into the ground.
        # Added light accumulates where discs overlap, so a cluster clips to
        # white unless each one contributes little. Scaled down again by how
        # light the disc already is.
        strength = alpha * (0.45 + 0.55 * z) * (1.0 - 0.45 * lightness)
        painter.setBrush(
            QColor(
                round(lit.red() * strength),
                round(lit.green() * strength),
                round(lit.blue() * strength),
            )
        )
        painter.drawEllipse(QRectF(x - radius, y - radius, radius * 2, radius * 2))
    painter.restore()


def _rings(painter, frame, pal, rng, colour_rng, depth) -> None:
    """Fine concentric outlines, drawn sharp over the soft discs."""
    w, h = frame.width, frame.height
    groups = rng.randint(2, 6)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for _ in range(groups):
        cx, cy = rng.uniform(0, w), rng.uniform(0, h)
        outer = frame.mm(rng.uniform(25.0, 70.0))
        count = rng.randint(6, 18)
        color = QColor(pal.pick(colour_rng.random()))
        color = shift(color, 0.22)
        color.setAlphaF(colour_rng.uniform(0.10, 0.26))
        painter.setPen(QPen(color, max(1.0, frame.mm(0.25))))
        for i in range(count):
            r = outer * (i + 1) / count
            painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
