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
from ..shading import capsule, cast_shadows, shape_brush, shift, underlay
from .base import pattern

# Rejected candidates are cheap and keeping the loop bounded matters more than
# hitting the target count exactly.
MAX_ATTEMPTS = 60

# How far a shape throws its shadow, as a fraction of its own size. Generous:
# these sit on open ground, unlike the tiling patterns where a shadow only ever
# lands in the seam between two touching tiles.
SHADOW_THROW = 0.15

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

    # Colour decisions follow the palette seed, placement follows the pattern
    # seed, so recolouring and relaying out are genuinely separate.
    colour_rng = pal.colour_rng()
    hue_field = field(colour_rng, terms=2, frequency=0.6)
    density = field(rng, terms=2, frequency=0.8)
    light = rng.uniform(0, math.tau)

    count = rng.randint(22, 48)
    largest = frame.mm(rng.uniform(45.0, 105.0))
    smallest = largest * rng.uniform(0.10, 0.22)
    # How sharply size falls away with distance. Without the bias most shapes
    # come out near the maximum and a few large ones swallow the frame.
    bias = rng.uniform(1.6, 3.2)
    threshold = rng.uniform(0.42, 0.66)
    stroke = colour_rng.random() < 0.45
    # Large, well-separated shapes can carry real hue differences -- it was
    # small adjacent cells that turned a multi-hue scheme into confetti.
    spread = colour_rng.choice((0.2, 0.45, 0.7, 1.0))
    # Enough to push the far shapes back, not enough to erase them.
    haze = colour_rng.uniform(0.18, 0.42) * depth

    shapes = []
    for _ in range(count):
        for _attempt in range(MAX_ATTEMPTS):
            x, y = rng.uniform(0, w), rng.uniform(0, h)
            # Clustered rather than uniform: shapes gather where the density
            # field is high and leave the rest of the frame open.
            if density(x / w, y / h) > threshold:
                break
        else:
            continue
        # Distance, not size, is the primary variable; size follows from it, so
        # a near shape is reliably the large sharp one.
        z = rng.random()
        size = smallest + (largest - smallest) * (z ** bias) * rng.uniform(0.8, 1.2)
        shapes.append((z, x, y, size))

    # Depth of field needs something in focus. Left to chance every shape can
    # land in a far band, and the whole image comes out soft with nothing to
    # rest on; stretching the distances up guarantees a foreground.
    if shapes:
        furthest = max(z for z, *_ in shapes)
        if furthest < BANDS[-1][0] + 0.15 and furthest > 0.0:
            stretch = (BANDS[-1][0] + 0.25) / furthest
            shapes = [(min(1.0, z * stretch), x, y, size) for z, x, y, size in shapes]

    shapes.sort()

    for low, high, divisor in BANDS:
        band = [s for s in shapes if low <= s[0] < high]
        if not band:
            continue
        if divisor == 1 or depth <= 0.0:
            _paint(painter, band, frame, pal, rng, colour_rng, light, spread, haze, hue_field, stroke, depth)
            continue

        # Painted small and enlarged: the softening is the point.
        layer = QImage(max(1, w // divisor), max(1, h // divisor), QImage.Format.Format_ARGB32_Premultiplied)
        layer.fill(Qt.GlobalColor.transparent)
        into = QPainter(layer)
        try:
            into.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            into.scale(1.0 / divisor, 1.0 / divisor)
            _paint(into, band, frame, pal, rng, colour_rng, light, spread, haze, hue_field, stroke, depth)
        finally:
            into.end()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawImage(QRect(0, 0, w, h), layer)


def _paint(painter, band, frame, pal, rng, colour_rng, light, spread, haze, hue_field, stroke, depth) -> None:
    w, h = frame.width, frame.height

    # Geometry first, so the whole band's shadows can be cast in one pass onto
    # the ground behind it rather than onto each other.
    placed = []
    for z, x, y, size in band:
        aspect = rng.choice((1.0, 1.0, rng.uniform(1.4, 3.4)))
        radius = size * rng.uniform(0.35, 0.5)
        angle = rng.uniform(0, math.tau)
        placed.append((z, x, y, size, capsule(x, y, size * aspect, size, radius, angle)))

    # Nearer shapes sit higher off the ground, so they throw further.
    cast_shadows(
        painter,
        frame,
        [(path, size * SHADOW_THROW * (0.35 + z)) for z, _x, _y, size, path in placed],
        light,
        depth,
        color=shift(pal.background, -0.22),
    )

    for z, x, y, size, path in placed:
        # A whole palette entry rather than a point along a ramp, so shapes can
        # differ in hue and not only in brightness. The field keeps neighbours
        # related; the jitter stops the image separating into bands of one
        # colour each.
        hue_t = hue_field(x / w, y / h) + colour_rng.uniform(-spread, spread)
        color = pal.pick(hue_t)
        # Depth still moves it, but only in lightness -- the hue is the one the
        # palette gave.
        color = shift(color, (z - 0.5) * 0.16)
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
