"""Post-processing.

Every effect is a whole-image QPainter composition rather than a Python pixel
loop -- at 3440x1440 that is five million pixels, and anything done per-pixel in
Python turns an instant render into a several-second one.
"""

from __future__ import annotations

import random
from typing import Mapping

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QRadialGradient

# Structural effects run before tonal ones, and film-like grain runs last, so a
# listing order of "grain, calm" and "calm, grain" produce the same image.
ORDER = ("calm", "darken", "vignette", "grain")

DEFAULT_STRENGTH = 0.6
GRAIN_TILE = 512

# Noise is incompressible, so a grained PNG is roughly twenty times the size of
# a flat one -- measured at 3440x1440, 0.3 MB becomes 7.7 MB. Worth knowing
# before it is switched on for every screen on a timer.
COSTLY = {
    "grain": "noise does not compress: PNGs grow roughly 20x (0.3 MB -> 7.7 MB at 3440x1440)",
}


def warning(name: str) -> str | None:
    """A caveat worth showing the user before an effect is enabled."""
    return COSTLY.get(name)


class UnknownEffect(ValueError):
    pass


def parse(spec: str) -> tuple[str, float]:
    """Parse "grain" or "grain=0.4"."""
    name, _, value = spec.partition("=")
    name = name.strip().lower()
    if name not in ORDER:
        raise UnknownEffect(f"unknown effect: {name}")
    if not value:
        return name, DEFAULT_STRENGTH
    try:
        strength = float(value)
    except ValueError as exc:
        raise UnknownEffect(f"{name}: not a number: {value}") from exc
    if not 0.0 <= strength <= 1.0:
        raise UnknownEffect(f"{name}: strength must be 0..1, got {strength}")
    return name, strength


def _fill(image: QImage, color: QColor, mode: QPainter.CompositionMode) -> None:
    painter = QPainter(image)
    painter.setCompositionMode(mode)
    painter.fillRect(image.rect(), color)
    painter.end()


def scale_range(image: QImage, gain: float, offset: float) -> None:
    """Map each channel to offset + value * gain, in place.

    Multiplying by a flat grey scales every channel; adding a flat grey lifts
    the floor. Together they are a levels adjustment done as two composites.
    """
    if gain < 1.0:
        level = round(255 * max(0.0, gain))
        _fill(image, QColor(level, level, level), QPainter.CompositionMode.CompositionMode_Multiply)
    if offset > 0.0:
        level = round(255 * min(1.0, offset))
        _fill(image, QColor(level, level, level), QPainter.CompositionMode.CompositionMode_Plus)


def desaturate(image: QImage, amount: float) -> None:
    """Blend toward the greyscale version, in place."""
    if amount <= 0.0:
        return
    grey = image.convertToFormat(QImage.Format.Format_Grayscale8)
    painter = QPainter(image)
    painter.setOpacity(min(1.0, amount))
    painter.drawImage(0, 0, grey)
    painter.end()


def fx_darken(image: QImage, strength: float, rng: random.Random) -> None:
    scale_range(image, 1.0 - 0.62 * strength, 0.0)


def fx_calm(image: QImage, strength: float, rng: random.Random, desaturate_by: float = 1.0) -> None:
    """The quiet mode: reduce what competes with the foreground.

    What makes a wallpaper distracting is local contrast between neighbouring
    shapes, not overall brightness -- a merely dimmed image is still busy. So
    this squeezes the tonal range toward the low end and pulls saturation down
    with it, which flattens shape-to-shape contrast while the pattern stays
    legible.
    """
    desaturate(image, 0.55 * strength * desaturate_by)
    scale_range(image, 1.0 - 0.52 * strength, 0.05 * strength)


def fx_vignette(image: QImage, strength: float, rng: random.Random) -> None:
    w, h = image.width(), image.height()
    if not w or not h:
        return
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    # The gradient is built as a circle and then squashed to the frame's aspect,
    # so the darkening reaches every edge by the same amount on a 21:9 panel and
    # on a portrait one alike.
    painter.translate(w / 2.0, h / 2.0)
    painter.scale(1.0, h / w)
    radius = w / 2.0 * 1.30
    gradient = QRadialGradient(QPointF(0.0, 0.0), radius)
    gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
    gradient.setColorAt(0.30, QColor(0, 0, 0, 0))
    gradient.setColorAt(1.0, QColor(0, 0, 0, round(235 * strength)))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(gradient))
    painter.drawRect(QRectF(-radius, -radius, radius * 2, radius * 2))
    painter.end()


def _grain_tile(strength: float, rng: random.Random) -> QImage:
    """A square of grey noise centred on mid-grey.

    Built from one call into the RNG's C implementation; generating half a
    million pixels one at a time in Python would dominate the whole render.
    """
    # Overlay is a strong operator; anything past a narrow spread stops
    # reading as film grain and starts reading as broadcast static.
    spread = 5 + round(19 * strength)
    raw = rng.randbytes(GRAIN_TILE * GRAIN_TILE)
    data = bytes(128 + ((b - 128) * spread) // 128 for b in raw)
    tile = QImage(data, GRAIN_TILE, GRAIN_TILE, GRAIN_TILE, QImage.Format.Format_Grayscale8)
    return tile.copy()  # detach from the local buffer


def fx_grain(image: QImage, strength: float, rng: random.Random) -> None:
    tile = _grain_tile(strength, rng)
    painter = QPainter(image)
    # Overlay leaves mid-grey untouched, so the noise modulates the image
    # instead of washing a flat haze over it.
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Overlay)
    painter.fillRect(image.rect(), QBrush(tile))
    painter.end()


APPLY = {
    "calm": fx_calm,
    "darken": fx_darken,
    "vignette": fx_vignette,
    "grain": fx_grain,
}


def apply_all(
    image: QImage,
    effects: Mapping[str, float],
    rng: random.Random,
    desaturate_by: float = 1.0,
) -> None:
    """Apply effects to the image in place, in the canonical order.

    `desaturate_by` scales back the quiet mode's desaturation. It exists because
    that step is there to rein in a generated palette, which can come out
    garish; a palette somebody chose is already at the saturation they wanted,
    and taking a third of it out again leaves grey.
    """
    for name in ORDER:
        strength = effects.get(name)
        if not strength:
            continue
        if name == "calm":
            fx_calm(image, float(strength), rng, desaturate_by)
        else:
            APPLY[name](image, float(strength), rng)
