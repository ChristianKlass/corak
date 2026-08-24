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
from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import (
    QBrush,
    QImage,
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QRadialGradient,
    QTransform,
)

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


def capsule(
    cx: float, cy: float, width: float, height: float, radius: float, angle: float
) -> QPainterPath:
    """A rounded rectangle, rotated about its own centre."""
    path = QPainterPath()
    path.addRoundedRect(-width / 2.0, -height / 2.0, width, height, radius, radius)
    transform = QTransform()
    transform.translate(cx, cy)
    transform.rotateRadians(angle)
    return transform.map(path)


def cast_shadows(
    painter: QPainter,
    frame,
    casters,
    light: float,
    strength: float = 1.0,
    divisor: int = 3,
    color: QColor | None = None,
) -> None:
    """Soft shadows for a group of shapes, in one pass.

    Painted small and drawn back at full size, which is a real penumbra rather
    than the hard edge a few stacked copies give. Done for a whole group so the
    shapes in it share one shadow plane and do not darken each other.

    Kept fairly tight. Softening it further stops reading as a shadow under a
    shape and starts reading as a general dimming of the whole image.
    """
    if strength <= 0.0 or not casters:
        return
    w, h = frame.width, frame.height
    small = QImage(
        max(1, w // divisor), max(1, h // divisor), QImage.Format.Format_ARGB32_Premultiplied
    )
    small.fill(Qt.GlobalColor.transparent)

    into = QPainter(small)
    try:
        into.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        into.scale(1.0 / divisor, 1.0 / divisor)
        into.setPen(Qt.PenStyle.NoPen)
        # Not pure black. A shadow is the ground with less light on it, so on a
        # pale theme black is a blot rather than a shadow.
        tone = QColor(color) if color is not None else QColor(0, 0, 0)
        tone.setAlpha(min(255, int(190 * strength)))
        into.setBrush(tone)
        for path, distance in casters:
            dx, dy = -math.cos(light) * distance, -math.sin(light) * distance
            into.translate(dx, dy)
            into.drawPath(path)
            into.translate(-dx, -dy)
    finally:
        into.end()

    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    painter.drawImage(QRect(0, 0, w, h), small)


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
