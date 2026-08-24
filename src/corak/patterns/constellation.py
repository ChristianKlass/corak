"""Points joined by lines.

Almost all ground and very little figure: a handful of nodes, the edges between
the near ones, and nothing else. It works because it is sparse -- joining every
pair turns it into a mesh, which is a different and much worse picture.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient

from ..frame import Frame
from ..noise import field
from ..palette import oklch, to_oklch
from ..shading import shift, underlay
from .base import pattern


@pattern("constellation")
def draw(painter: QPainter, frame: Frame, rng, pal) -> None:
    w, h = frame.width, frame.height
    depth = frame.depth
    underlay(painter, frame, pal, rng, depth * 0.6)

    colour_rng = pal.colour_rng()
    hue_field = field(colour_rng, terms=2, frequency=0.6)
    density = field(rng, terms=2, frequency=0.9)
    spread = colour_rng.choice((0.25, 0.5, 0.9))

    count = rng.randint(22, 55)
    reach = frame.mm(rng.uniform(70.0, 150.0))
    node_size = frame.mm(rng.uniform(1.6, 4.0))
    threshold = rng.uniform(0.12, 0.35)

    nodes = []
    for _ in range(count):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        if density(x / w, y / h) < threshold:
            continue
        hue_t = hue_field(x / w, y / h) + colour_rng.uniform(-spread, spread)
        # Lifted well clear of the ground. A node that takes whatever palette
        # entry it lands on is invisible half the time, and the whole picture
        # is the points -- there is nothing else in it to carry the image.
        nodes.append((QPointF(x, y), shift(pal.pick(hue_t), 0.22)))

    # Each node reaches only to its nearest few. Joining everything within the
    # radius produces a mesh; the picture is in what is left out.
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for i, (point, color) in enumerate(nodes):
        near = sorted(
            ((math.dist((point.x(), point.y()), (other.x(), other.y())), j)
             for j, (other, _c) in enumerate(nodes) if j != i),
        )[: rng.randint(1, 3)]
        for distance, j in near:
            if distance > reach:
                continue
            line = QColor(color)
            # Faded with length, so the long edges read as further away.
            line.setAlphaF(max(0.22, 0.85 * (1.0 - distance / reach)))
            painter.setPen(QPen(line, max(1.0, frame.mm(0.35))))
            painter.drawLine(point, nodes[j][0])

    painter.setPen(Qt.PenStyle.NoPen)
    glow_reach = rng.uniform(3.5, 7.0)
    for point, color in nodes:
        size = node_size * rng.uniform(0.6, 1.6)

        # Added rather than blended: a translucent dark colour laid over a dark
        # ground is invisible, and light is what a glow is made of. The colour
        # is lifted to a floor rather than by a step, since brightening an
        # already dark palette entry leaves almost nothing to add.
        lightness, chroma, hue = to_oklch(color)
        lit = oklch(max(0.82, lightness + 0.3), chroma * 0.8, hue)
        reach = size * glow_reach

        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        halo = QRadialGradient(point, reach)
        # A slow falloff. Collapsing to nothing within a third of the radius
        # leaves a dot with a rim rather than a light with a halo.
        for stop, strength in ((0.0, 0.75), (0.10, 0.40), (0.30, 0.15), (0.60, 0.05), (1.0, 0.0)):
            halo.setColorAt(
                stop,
                QColor(
                    round(lit.red() * strength),
                    round(lit.green() * strength),
                    round(lit.blue() * strength),
                ),
            )
        painter.setBrush(halo)
        painter.drawEllipse(QRectF(point.x() - reach, point.y() - reach, reach * 2, reach * 2))
        painter.restore()

        painter.setBrush(shift(color, 0.18))
        painter.drawEllipse(QRectF(point.x() - size, point.y() - size, size * 2, size * 2))
