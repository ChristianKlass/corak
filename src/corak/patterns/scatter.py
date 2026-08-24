"""Loose shapes in depth.

A lattice fills every pixel and reads as texture. What makes a wallpaper look
composed is the opposite: a few large shapes, more small ones, clustered
somewhere and absent elsewhere, with the background left visible between them.

Depth comes from three cues used together, because stacking alone only ever
looks like stacked paper:

  z-order and cast shadows -- which shape is in front
  aerial perspective       -- distant shapes fade toward the background
  depth of field           -- distant shapes are out of focus
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QImage, QPainter, QPen

from ..frame import Frame
from ..noise import field
from ..palette import blend_direct
from ..shading import capsule, drop_shadow, shape_brush, shift, underlay
from .base import pattern

# Rejected candidates are cheap and keeping the loop bounded matters more than
# hitting the target count exactly.
MAX_ATTEMPTS = 60

# Far to near. The divisor is how much a band is shrunk before being drawn back
# at full size, which is what puts it out of focus: a real gaussian at wallpaper
# resolution costs seconds, and a downscale-upscale is indistinguishable at
# these radii.
BANDS = ((0.00, 0.34, 9), (0.34, 0.70, 3), (0.70, 1.01, 1))


@pattern("scatter")
def draw(painter: QPainter, frame: Frame, rng, pal) -> None:
    w, h = frame.width, frame.height
    depth = frame.depth
    underlay(painter, frame, pal, rng, depth)

    hue_field = field(rng, terms=2)
    density = field(rng, terms=2)
    light = rng.uniform(0, math.tau)

    count = rng.randint(16, 40)
    largest = frame.mm(rng.uniform(45.0, 105.0))
    smallest = largest * rng.uniform(0.10, 0.22)
    # How sharply size falls away with distance. Without the bias most shapes
    # come out near the maximum and a few large ones swallow the frame.
    bias = rng.uniform(1.6, 3.2)
    threshold = rng.uniform(0.42, 0.66)
    stroke = rng.random() < 0.45
    # Large, well-separated shapes can carry real hue differences -- it was
    # small adjacent cells that turned a multi-hue scheme into confetti.
    spread = rng.choice((0.05, 0.15, 0.45, 0.8))
    # Enough to push the far shapes back, not enough to erase them.
    haze = rng.uniform(0.25, 0.55) * depth

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
        # Distance, not size, is the primary variable; size follows from it, so
        # a near shape is reliably the large sharp one.
        z = rng.random()
        size = smallest + (largest - smallest) * (z ** bias) * rng.uniform(0.8, 1.2)
        shapes.append((z, x, y, size))

    shapes.sort()

    for low, high, divisor in BANDS:
        band = [s for s in shapes if low <= s[0] < high]
        if not band:
            continue
        if divisor == 1 or depth <= 0.0:
            _paint(painter, band, frame, pal, rng, light, spread, haze, hue_field, stroke, depth)
            continue

        # Painted small and enlarged: the softening is the point.
        layer = QImage(max(1, w // divisor), max(1, h // divisor), QImage.Format.Format_ARGB32_Premultiplied)
        layer.fill(Qt.GlobalColor.transparent)
        into = QPainter(layer)
        try:
            into.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            into.scale(1.0 / divisor, 1.0 / divisor)
            _paint(into, band, frame, pal, rng, light, spread, haze, hue_field, stroke, depth)
        finally:
            into.end()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawImage(QRect(0, 0, w, h), layer)


def _paint(painter, band, frame, pal, rng, light, spread, haze, hue_field, stroke, depth) -> None:
    w, h = frame.width, frame.height
    for z, x, y, size in band:
        aspect = rng.choice((1.0, 1.0, rng.uniform(1.4, 3.4)))
        radius = size * rng.uniform(0.35, 0.5)
        angle = rng.uniform(0, math.tau)
        path = capsule(x, y, size * aspect, size, radius, angle)

        # Nearer shapes sit higher off the ground, so they cast further.
        drop_shadow(painter, path, light, size * 0.10 * depth * (0.4 + z), depth * (0.4 + z))

        hue_t = hue_field(x / w * 1.3, y / h * 1.3) + rng.uniform(-spread, spread)
        color = pal.shade(hue_t, 0.30 + 0.55 * z + rng.uniform(-0.07, 0.07))
        # Aerial perspective: distance pulls a shape toward the background, so
        # the far ones sit back instead of competing with the near ones.
        color = blend_direct(pal.background, color, 1.0 - haze * (1.0 - z))

        painter.setBrush(
            shape_brush(color, QPointF(x, y), size, light, depth) if depth else color
        )
        painter.setPen(
            QPen(shift(color, 0.12), max(1.0, size * 0.008)) if stroke else QPen(color, 1.0)
        )
        painter.drawPath(path)
