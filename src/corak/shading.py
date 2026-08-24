"""Depth: gradients and shadows.

Flat fills are what make generated wallpapers look generated. Real ones are
shaded -- a large gradient under everything, another across each shape, and
enough of a shadow to say which shape is in front. None of it is expensive:
they are all QPainter brushes.

Kept deliberately subtle. A strong per-shape gradient stops reading as a lit
surface and starts reading as an inflated bubble, which no amount of colour
work recovers from.
"""

from __future__ import annotations

import math
from PySide6.QtCore import QPointF
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QRadialGradient

from .frame import Frame
from .palette import oklch, to_oklch


def shift(color: QColor, amount: float, chroma: float = 1.0) -> QColor:
    """Lighten or darken perceptually, optionally pulling chroma with it."""
    lightness, c, hue = to_oklch(color)
    return oklch(lightness + amount, c * chroma, hue)


def underlay(painter: QPainter, frame: Frame, pal, rng, strength: float = 1.0) -> None:
    """Paint the large-scale gradient everything else sits on.

    A single gradient across the whole frame is most of what separates a
    designed wallpaper from a tiling: it gives the image somewhere to be bright
    and somewhere to be dark, which no amount of per-cell variation supplies.
    """
    if rng.random() < 0.72:
        angle = rng.uniform(0, math.tau)
        length = frame.diagonal * 0.55
        centre = QPointF(frame.width / 2.0, frame.height / 2.0)
        gradient = QLinearGradient(
            centre + QPointF(math.cos(angle) * -length, math.sin(angle) * -length),
            centre + QPointF(math.cos(angle) * length, math.sin(angle) * length),
        )
    else:
        gradient = QRadialGradient(
            QPointF(frame.width * rng.uniform(0.2, 0.8), frame.height * rng.uniform(0.2, 0.8)),
            frame.diagonal * rng.uniform(0.55, 0.9),
        )
    spread = 0.16 * strength
    gradient.setColorAt(0.0, shift(pal.background, spread))
    gradient.setColorAt(1.0, shift(pal.background, -spread * 0.7))
    painter.fillRect(0, 0, frame.width, frame.height, QBrush(gradient))


def shape_brush(
    color: QColor,
    centre: QPointF,
    radius: float,
    light: float,
    strength: float = 1.0,
) -> QBrush:
    """A gradient across one shape, lit from a shared direction."""
    offset = QPointF(math.cos(light) * radius, math.sin(light) * radius)
    gradient = QLinearGradient(centre - offset, centre + offset)
    spread = 0.032 * strength
    gradient.setColorAt(0.0, shift(color, spread, 0.95))
    gradient.setColorAt(1.0, shift(color, -spread, 1.05))
    return QBrush(gradient)


def drop_shadow(
    painter: QPainter,
    path: QPainterPath,
    light: float,
    distance: float,
    strength: float = 1.0,
) -> None:
    """A soft shadow, built from a few offset copies rather than a blur.

    A real gaussian over a 4K frame costs seconds; three translucent copies at
    increasing offsets read the same at this scale and cost nothing.
    """
    if strength <= 0.0 or distance <= 0.0:
        return
    dx, dy = -math.cos(light) * distance, -math.sin(light) * distance
    painter.save()
    painter.setPen(QColor(0, 0, 0, 0))
    # Three copies stack, so each has to be faint: at full strength they were
    # closing to near-black webbing between neighbouring shapes.
    for step in (1.0, 0.66, 0.33):
        painter.setBrush(QColor(0, 0, 0, int(13 * strength * step)))
        painter.translate(dx * step, dy * step)
        painter.drawPath(path)
        painter.translate(-dx * step, -dy * step)
    painter.restore()
