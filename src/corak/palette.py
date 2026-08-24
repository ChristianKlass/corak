"""Colour scheme generation, in a perceptual space.

Ramps are built in OKLab rather than HSL. HSL lightness is not perceptual --
equal steps in it do not look like equal steps, yellows blow out while blues go
muddy, and interpolating between two hues passes through a desaturated dip. In
OKLab a lightness ramp reads as even and a blend between two colours stays as
vivid as its ends.
"""

from __future__ import annotations

import math
import random
from typing import Iterable, Sequence

from PySide6.QtGui import QColor

RAMP_STOPS = 5
GAMUT_STEPS = 14

# Hue offsets in turns, relative to the base hue. Weighted rather than uniform:
# the tight schemes read as deliberate at wallpaper scale, while triads applied
# across a whole screen tend to look like a test card.
SCHEMES: dict[str, Sequence[float]] = {
    "mono": (0.0,),
    "analogous": (-0.08, 0.0, 0.08),
    "complement": (0.0, 0.5),
    "split": (0.0, 0.42, 0.58),
    "triad": (0.0, 1 / 3, 2 / 3),
}
SCHEME_WEIGHTS = {
    "mono": 26,
    "analogous": 34,
    "complement": 16,
    "split": 14,
    "triad": 10,
}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _to_linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def _from_linear(channel: float) -> float:
    return channel * 12.92 if channel <= 0.0031308 else 1.055 * channel ** (1 / 2.4) - 0.055


def oklab_to_rgb(ll: float, a: float, b: float) -> tuple[float, float, float]:
    """OKLab to linear-light sRGB. Channels may fall outside 0..1."""
    l_ = ll + 0.3963377774 * a + 0.2158037573 * b
    m_ = ll - 0.1055613458 * a - 0.0638541728 * b
    s_ = ll - 0.0894841775 * a - 1.2914855480 * b
    l3, m3, s3 = l_ * l_ * l_, m_ * m_ * m_, s_ * s_ * s_
    return (
        4.0767416621 * l3 - 3.3077115913 * m3 + 0.2309699292 * s3,
        -1.2684380046 * l3 + 2.6097574011 * m3 - 0.3413193965 * s3,
        -0.0041960863 * l3 - 0.7034186147 * m3 + 1.7076147010 * s3,
    )


def rgb_to_oklab(r: float, g: float, b: float) -> tuple[float, float, float]:
    """Linear-light sRGB to OKLab."""
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = _cbrt(l), _cbrt(m), _cbrt(s)
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def _cbrt(value: float) -> float:
    return math.copysign(abs(value) ** (1 / 3), value)


def _in_gamut(rgb: tuple[float, float, float]) -> bool:
    return all(-1e-4 <= c <= 1 + 1e-4 for c in rgb)


def oklch(lightness: float, chroma: float, hue_turns: float) -> QColor:
    """A colour from perceptual lightness, chroma and hue.

    Chroma is reduced until the colour fits sRGB, rather than each channel being
    clipped independently -- clipping shifts the hue, which is exactly what a
    perceptual space is being used to avoid.
    """
    lightness = _clamp(lightness)
    angle = (hue_turns % 1.0) * math.tau
    cos_h, sin_h = math.cos(angle), math.sin(angle)

    low, high = 0.0, max(0.0, chroma)
    if _in_gamut(oklab_to_rgb(lightness, high * cos_h, high * sin_h)):
        low = high
    else:
        for _ in range(GAMUT_STEPS):
            middle = (low + high) / 2.0
            if _in_gamut(oklab_to_rgb(lightness, middle * cos_h, middle * sin_h)):
                low = middle
            else:
                high = middle

    return _from_oklab(lightness, low * cos_h, low * sin_h)


def to_oklab(color: QColor) -> tuple[float, float, float]:
    return rgb_to_oklab(
        _to_linear(color.redF()), _to_linear(color.greenF()), _to_linear(color.blueF())
    )


def to_oklch(color: QColor) -> tuple[float, float, float]:
    """Perceptual lightness, chroma, and hue in turns."""
    lightness, a, b = to_oklab(color)
    return lightness, math.hypot(a, b), (math.atan2(b, a) / math.tau) % 1.0


def blend(first: QColor, second: QColor, t: float) -> QColor:
    """Interpolate perceptually, so the midpoint does not go grey.

    Polar, along the shorter way round the hue circle. A straight line through
    OKLab between two well-separated hues passes close to the neutral axis, so
    the middle of a triad ramp would wash out to grey -- which is the muddiness
    a perceptual space was supposed to fix.
    """
    t = _clamp(t)
    l1, c1, h1 = to_oklch(first)
    l2, c2, h2 = to_oklch(second)

    # A neutral colour has no meaningful hue, so it borrows the other's rather
    # than dragging the blend halfway around the circle.
    if c1 < 1e-4:
        h1 = h2
    elif c2 < 1e-4:
        h2 = h1

    delta = (h2 - h1 + 0.5) % 1.0 - 0.5
    return oklch(l1 + (l2 - l1) * t, c1 + (c2 - c1) * t, h1 + delta * t)


def blend_direct(first: QColor, second: QColor, t: float) -> QColor:
    """Interpolate in a straight line through OKLab.

    For a palette somebody chose, this is the honest blend: it stays between the
    two colours instead of travelling round the hue circle and inventing ones
    that are not in the set -- blue to rust by the polar route passes through
    green.
    """
    t = _clamp(t)
    l1, a1, b1 = to_oklab(first)
    l2, a2, b2 = to_oklab(second)
    return _from_oklab(l1 + (l2 - l1) * t, a1 + (a2 - a1) * t, b1 + (b2 - b1) * t)


def _from_oklab(lightness: float, a: float, b: float) -> QColor:
    red, green, blue = oklab_to_rgb(lightness, a, b)
    return QColor.fromRgbF(
        _clamp(_from_linear(_clamp(red))),
        _clamp(_from_linear(_clamp(green))),
        _clamp(_from_linear(_clamp(blue))),
    )


class Palette:
    """An ordered colour ramp plus a background colour."""

    def __init__(
        self,
        seed: int,
        dark: bool | None = None,
        scheme: str | None = None,
        schemes: Sequence[str] | None = None,
        hue_range: tuple[float, float] | None = None,
        chroma_range: tuple[float, float] | None = None,
        lightness_range: tuple[float, float] | None = None,
    ) -> None:
        self.seed = seed
        rng = random.Random(seed)
        # The draw happens either way: consuming it only when `dark` is unset
        # would shift the rest of the stream, so forcing a dark palette would
        # silently change the hue and scheme too.
        roll = rng.random()
        self.dark = roll < 0.68 if dark is None else dark

        if scheme is None:
            allowed = [s for s in (schemes or ()) if s in SCHEMES] or list(SCHEME_WEIGHTS)
            scheme = rng.choices(allowed, weights=[SCHEME_WEIGHTS[s] for s in allowed])[0]
        elif scheme not in SCHEMES:
            raise ValueError(f"unknown scheme: {scheme}")
        self.scheme = scheme

        offsets = SCHEMES[scheme]
        if hue_range:
            # The range is the whole colour budget, not just where the base hue
            # may sit: a split scheme's offsets reach 0.58 of a turn away, which
            # would carry a blue theme into brown. The offsets are compressed to
            # fit, and the base is placed so every one of them lands inside.
            low, high = hue_range
            span = high - low
            reach = max(offsets) - min(offsets)
            if reach > span:
                factor = span / reach
                offsets = tuple(o * factor for o in offsets)
            self.base_hue = rng.uniform(low - min(offsets), high - max(offsets)) % 1.0
        else:
            self.base_hue = rng.random()
        self.chroma = rng.uniform(*(chroma_range or (0.045, 0.16)))
        # Below roughly 0.75 the yellow-green quarter of the wheel turns to
        # khaki, so a pale theme has to say where its lightness sits rather
        # than inheriting a range chosen for dark ones.
        lo, hi = lightness_range or ((0.32, 0.72) if self.dark else (0.62, 0.93))

        self._offsets = tuple(offsets)
        self._lightness = (lo, hi)
        self._generated = True

        self.colors = []
        for i in range(RAMP_STOPS):
            t = i / (RAMP_STOPS - 1)
            # Walking the offsets in order rather than sampling them randomly
            # means the ramp moves through the scheme instead of jumping about.
            hue = self.base_hue + offsets[round(t * (len(offsets) - 1))]
            self.colors.append(
                oklch(
                    lo + (hi - lo) * t,
                    self.chroma * rng.uniform(0.82, 1.14),
                    hue + rng.uniform(-0.012, 0.012),
                )
            )

        # A light background sits just above its own ramp rather than at a
        # fixed near-white: pinning it to white makes any light theme glare,
        # whatever lightness its shapes were given.
        self.background = oklch(
            rng.uniform(0.13, 0.21)
            if self.dark
            else min(0.985, hi + rng.uniform(0.02, 0.08)),
            self.chroma * 0.45,
            self.base_hue + offsets[0],
        )

        # Traversing the whole ramp in one image usually reads as muddy; most
        # look better confined to a slice of it.
        width = rng.uniform(0.55, 1.0)
        self._t0 = rng.uniform(0.0, 1.0 - width)
        self._t1 = self._t0 + width

    @classmethod
    def for_theme(cls, seed: int, theme, dark: bool | None = None) -> "Palette":
        """A palette obeying a theme's colour constraints."""
        if getattr(theme, "colors", ()):
            return cls.from_hex(
                theme.colors, dark=theme.dark if dark is None else dark, seed=seed
            )
        return cls(
            seed,
            dark=theme.dark if dark is None else dark,
            schemes=theme.schemes or None,
            hue_range=theme.hue_range,
            chroma_range=theme.chroma,
            lightness_range=theme.lightness,
        )

    @classmethod
    def from_hex(
        cls, codes: Iterable[str], dark: bool | None = None, seed: int | None = None
    ) -> "Palette":
        """Build a palette from explicit hex codes, ordered dark to light.

        The seed does not invent colours -- the point of giving a palette is
        that it is the one used -- but it does choose how much of it a single
        wallpaper draws on. Without that, rerolling the colours of a fixed
        palette produces an identical image and the control appears broken.
        """
        colors = []
        for code in codes:
            color = QColor(code if code.startswith("#") else f"#{code}")
            if not color.isValid():
                raise ValueError(f"not a colour: {code}")
            colors.append(color)
        if not colors:
            raise ValueError("at least one colour is required")

        # Sorted by perceptual lightness, so the ramp climbs the way the eye
        # reads it rather than the way HSL happens to number it.
        colors.sort(key=lambda c: to_oklab(c)[0])

        if seed is not None:
            # A palette describes a region of colour space, not five exact
            # points. Rerolling the colours has to be able to reach a more
            # saturated version of the theme, or the only way to escape a muted
            # image is to change theme entirely -- and chroma that can only fall
            # means every reroll is a step further toward grey.
            vary = random.Random(seed ^ 0x5EED)
            turn = vary.uniform(-0.07, 0.07)
            lift = vary.uniform(-0.05, 0.05)
            # Aimed at an absolute chroma rather than scaled by a factor: a
            # palette written at 0.04 cannot be multiplied into a colourful one
            # without the multiplier being absurd for a palette written at 0.15.
            # Weighted toward what the theme asked for, but able to reach past
            # it, so a muted theme still has a vivid variant in it.
            strongest = max(to_oklch(c)[1] for c in colors) or 0.001
            target = vary.choices(
                (strongest, strongest * 0.7, 0.07, 0.10, 0.14),
                weights=(34, 16, 18, 18, 14),
            )[0]
            gain = min(6.0, target / strongest)
            colors = [
                oklch(lightness + lift, chroma * gain, hue + turn)
                for lightness, chroma, hue in (to_oklch(c) for c in colors)
            ]
        palette = cls.__new__(cls)
        palette.seed = -1
        palette.scheme = "custom"
        palette.base_hue = max(colors[-1].hueF(), 0.0)
        palette.chroma = 0.0
        palette.colors = colors
        middle = to_oklab(colors[len(colors) // 2])[0]
        palette.dark = middle < 0.5 if dark is None else dark
        lightness, _, _ = to_oklab(colors[0] if palette.dark else colors[-1])
        palette.background = oklch(
            _clamp(lightness * 0.55) if palette.dark else _clamp(lightness * 1.06),
            0.02,
            palette.base_hue,
        )
        palette._reverse = False
        if seed is None:
            palette._t0, palette._t1 = 0.0, 1.0
        else:
            rng = random.Random(seed)
            width = rng.uniform(0.35, 1.0)
            palette._t0 = rng.uniform(0.0, 1.0 - width)
            palette._t1 = palette._t0 + width
            # Running the ramp the other way puts the pale colours where the
            # dark ones were. It is the largest change available without
            # inventing a colour the palette does not contain.
            palette._reverse = rng.random() < 0.4
        palette.seed = -1 if seed is None else seed
        palette._generated = False
        palette._offsets = (0.0,)
        palette._lightness = (0.0, 1.0)
        return palette

    def colour_rng(self) -> random.Random:
        """A generator tied to the palette rather than to the geometry.

        Which shape gets which colour is a colour decision, so it has to follow
        the palette seed. Taken from the pattern's generator instead, rerolling
        the colours leaves every shape holding the colour it already had.
        """
        return random.Random((self.seed if self.seed >= 0 else 0) ^ 0x9E3779B9)

    def hue_at(self, t: float) -> float:
        """The scheme's hue a fraction of the way along it."""
        offsets = self._offsets
        if len(offsets) == 1:
            return self.base_hue + offsets[0]
        pos = _clamp(t) * (len(offsets) - 1)
        i = min(int(pos), len(offsets) - 2)
        return self.base_hue + offsets[i] + (offsets[i + 1] - offsets[i]) * (pos - i)

    def shade(self, hue_t: float, light_t: float, chroma: float = 1.0) -> QColor:
        """A colour with hue and lightness chosen independently.

        Driving both from one value is what turns a multi-hue scheme into
        confetti: a small change in a spatial field then crosses a hue boundary,
        so neighbouring shapes jump from orange to blue. Given separate inputs a
        pattern can let hue drift slowly across the whole image while lightness
        varies shape to shape, which is what reads as coherent.
        """
        if not getattr(self, "_generated", False):
            # A given palette has no hue formula to sample, so the slow field
            # chooses which of its colours to use and the fast one only shades
            # that colour up or down. Letting the fast field pick the colour
            # instead would jump between palette entries shape to shape.
            # Position along a given palette follows both inputs. Taking hue
            # alone left a near shape no way to reach the pale end, so a
            # scattered pattern sampled the middle of every palette and came
            # out uniformly dark. Consecutive palette entries are neighbours,
            # so letting the faster input move the position too costs nothing.
            position = _clamp(0.6 * _clamp(hue_t) + 0.4 * _clamp(light_t))
            base = self.ramp(position)
            lightness, c, hue = to_oklch(base)
            return oklch(lightness + (_clamp(light_t) - 0.5) * 0.10, c * chroma, hue)
        lo, hi = self._lightness
        # The same cohesion slice the ramp uses: most images look better over
        # part of the scheme than over all of it.
        span = self._t0 + (self._t1 - self._t0) * _clamp(hue_t)
        return oklch(lo + (hi - lo) * _clamp(light_t), self.chroma * chroma, self.hue_at(span))

    def pick(self, t: float, rng: random.Random | None = None) -> QColor:
        """One of the palette's colours, chosen whole.

        Interpolating along a ramp can only ever give a shape a brightness --
        every shape comes out the same hue. Taking an entry as written is what
        lets one shape be teal and the next magenta, which is the difference
        between a gradient and a colour scheme.
        """
        if not self.colors:
            return QColor(0, 0, 0)
        index = min(len(self.colors) - 1, max(0, int(_clamp(t) * len(self.colors))))
        return self.colors[index]

    def ramp(self, t: float, full: bool = False) -> QColor:
        """Sample the ramp. t is 0..1; `full` ignores the cohesion slice."""
        t = _clamp(t)
        if getattr(self, "_reverse", False):
            t = 1.0 - t
        if not full:
            t = self._t0 + (self._t1 - self._t0) * t
        if len(self.colors) == 1:
            return self.colors[0]
        pos = t * (len(self.colors) - 1)
        i = min(int(pos), len(self.colors) - 2)
        # Generated ramps take the polar route, which keeps chroma up between
        # distant hues; a given palette takes the direct one, which invents no
        # colours its author did not pick.
        mix = blend if getattr(self, "_generated", False) else blend_direct
        return mix(self.colors[i], self.colors[i + 1], pos - i)
