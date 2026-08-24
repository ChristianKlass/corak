"""Effects and palettes."""

from __future__ import annotations

import os
import tempfile
import random
import statistics
import unittest

# Tests must not see the running user's installed themes or settings: a theme
# dropped into the real config directory would otherwise change what they mean.
_isolated = tempfile.mkdtemp(prefix="corak-tests-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_isolated, "config")
os.environ["XDG_DATA_HOME"] = os.path.join(_isolated, "data")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402

_app = QGuiApplication.instance() or QGuiApplication([])

from corak import effects as fx  # noqa: E402
from corak import shading  # noqa: E402
from corak.frame import Frame  # noqa: E402
from corak.engine import Engine  # noqa: E402
from corak.palette import SCHEMES, Palette, blend, oklch, to_oklab  # noqa: E402

SIZE = (240, 140)


def _samples(image):
    step = 7
    return [
        image.pixelColor(x, y)
        for y in range(0, image.height(), step)
        for x in range(0, image.width(), step)
    ]


def _mean_value(image) -> float:
    return statistics.fmean(c.valueF() for c in _samples(image))


def _mean_saturation(image) -> float:
    return statistics.fmean(c.saturationF() for c in _samples(image))


def _contrast(image) -> float:
    return statistics.pstdev([c.valueF() for c in _samples(image)])


class TestParse(unittest.TestCase):
    def test_bare_name_gets_the_default_strength(self) -> None:
        self.assertEqual(fx.parse("grain"), ("grain", fx.DEFAULT_STRENGTH))

    def test_explicit_strength(self) -> None:
        self.assertEqual(fx.parse("calm=0.25"), ("calm", 0.25))

    def test_unknown_name_rejected(self) -> None:
        with self.assertRaises(fx.UnknownEffect):
            fx.parse("sparkle")

    def test_out_of_range_rejected(self) -> None:
        with self.assertRaises(fx.UnknownEffect):
            fx.parse("grain=4")

    def test_non_numeric_rejected(self) -> None:
        with self.assertRaises(fx.UnknownEffect):
            fx.parse("grain=lots")


class TestEffects(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = Engine()
        self.design = self.engine.new_design(random.Random(9), pattern="triangles")

    def render(self, effects=None):
        return self.engine.render(self.design, *SIZE, effects)

    def test_calm_reduces_contrast_and_saturation(self) -> None:
        plain, calm = self.render(), self.render({"calm": 0.8})
        self.assertLess(_contrast(calm), _contrast(plain))
        self.assertLess(_mean_saturation(calm), _mean_saturation(plain))

    def test_darken_lowers_brightness(self) -> None:
        self.assertLess(_mean_value(self.render({"darken": 0.7})), _mean_value(self.render()))

    def test_vignette_darkens_corners_not_the_centre(self) -> None:
        plain, shaded = self.render(), self.render({"vignette": 0.9})
        w, h = SIZE
        self.assertLess(shaded.pixelColor(2, 2).valueF(), plain.pixelColor(2, 2).valueF())
        self.assertAlmostEqual(
            shaded.pixelColor(w // 2, h // 2).valueF(),
            plain.pixelColor(w // 2, h // 2).valueF(),
            places=2,
        )

    def test_grain_adds_pixel_to_pixel_variation(self) -> None:
        def neighbour_delta(image) -> float:
            return statistics.fmean(
                abs(image.pixelColor(x, 40).valueF() - image.pixelColor(x + 1, 40).valueF())
                for x in range(20, 200)
            )

        self.assertGreater(neighbour_delta(self.render({"grain": 0.8})), neighbour_delta(self.render()))

    def test_effects_apply_in_a_fixed_order(self) -> None:
        a = self.render({"grain": 0.5, "calm": 0.6})
        b = self.render({"calm": 0.6, "grain": 0.5})
        self.assertEqual(a, b)

    def test_effects_are_reproducible(self) -> None:
        self.assertEqual(self.render({"grain": 0.5}), self.render({"grain": 0.5}))

    def test_zero_strength_is_a_no_op(self) -> None:
        self.assertEqual(self.render({"grain": 0.0}), self.render())


class TestPalette(unittest.TestCase):
    def test_every_scheme_builds(self) -> None:
        for scheme in SCHEMES:
            with self.subTest(scheme=scheme):
                palette = Palette(3, scheme=scheme)
                self.assertEqual(palette.scheme, scheme)
                self.assertTrue(all(c.isValid() for c in palette.colors))

    def test_unknown_scheme_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Palette(3, scheme="octarine")

    def test_forcing_dark_keeps_the_same_hues(self) -> None:
        # Consuming the RNG differently would silently change scheme and hue,
        # so toggling the quiet mode would recolour the wallpaper.
        loose, forced = Palette(77), Palette(77, dark=True)
        self.assertEqual(loose.scheme, forced.scheme)
        self.assertAlmostEqual(loose.base_hue, forced.base_hue)

    def test_dark_palette_has_a_dark_background(self) -> None:
        self.assertLess(Palette(5, dark=True).background.lightnessF(), 0.25)
        self.assertGreater(Palette(5, dark=False).background.lightnessF(), 0.75)

    def test_from_hex_orders_dark_to_light(self) -> None:
        palette = Palette.from_hex(["#ffffff", "224466", "#88aa44"])
        lightness = [c.lightnessF() for c in palette.colors]
        self.assertEqual(lightness, sorted(lightness))

    def test_from_hex_rejects_nonsense(self) -> None:
        with self.assertRaises(ValueError):
            Palette.from_hex(["not-a-colour"])
        with self.assertRaises(ValueError):
            Palette.from_hex([])

    def test_ramp_is_clamped(self) -> None:
        palette = Palette(11)
        self.assertEqual(palette.ramp(-5.0).name(), palette.ramp(0.0).name())
        self.assertEqual(palette.ramp(5.0).name(), palette.ramp(1.0).name())


class TestPerceptualColour(unittest.TestCase):
    """Ramps are built in OKLab, not HSL."""

    def test_oklch_round_trips(self) -> None:
        for lightness, chroma, hue in [(0.3, 0.08, 0.1), (0.6, 0.12, 0.55), (0.85, 0.04, 0.9)]:
            with self.subTest(l=lightness, c=chroma, h=hue):
                back = to_oklab(oklch(lightness, chroma, hue))[0]
                self.assertAlmostEqual(back, lightness, places=2)

    def test_impossible_chroma_is_reduced_not_clipped(self) -> None:
        # Clipping each channel would shift the hue, which is the whole reason
        # for working in a perceptual space.
        colour = oklch(0.5, 0.9, 0.7)
        self.assertTrue(all(0.0 <= c <= 1.0 for c in (colour.redF(), colour.greenF(), colour.blueF())))
        self.assertAlmostEqual(to_oklab(colour)[0], 0.5, places=2)

    def test_ramp_lightness_climbs_evenly(self) -> None:
        palette = Palette(21, dark=False)
        steps = [to_oklab(c)[0] for c in palette.colors]
        self.assertEqual(steps, sorted(steps))
        gaps = [b - a for a, b in zip(steps, steps[1:])]
        # Even to within a fifth of the mean step; HSL cannot promise this.
        self.assertLess(max(gaps) - min(gaps), statistics.fmean(gaps) * 0.2)

    def test_blending_two_hues_does_not_go_grey(self) -> None:
        def chroma(colour):
            _, a, b = to_oklab(colour)
            return (a * a + b * b) ** 0.5

        first, second = oklch(0.6, 0.13, 0.05), oklch(0.6, 0.13, 0.4)
        midpoint = blend(first, second, 0.5)
        self.assertGreater(chroma(midpoint), min(chroma(first), chroma(second)) * 0.75)

    def test_from_hex_orders_by_perceptual_lightness(self) -> None:
        palette = Palette.from_hex(["#ffff00", "#0000ff", "#808080"])
        steps = [to_oklab(c)[0] for c in palette.colors]
        self.assertEqual(steps, sorted(steps))
        # Yellow is perceptually the lightest even though HSL calls it 0.5.
        self.assertEqual(palette.colors[-1].name(), "#ffff00")


class TestShading(unittest.TestCase):
    """Depth: gradients, shadows, rounded corners."""

    def test_shift_moves_lightness_without_moving_hue(self) -> None:
        from corak.palette import oklch, to_oklch

        base = oklch(0.5, 0.1, 0.6)
        lighter, darker = shading.shift(base, 0.1), shading.shift(base, -0.1)
        self.assertAlmostEqual(to_oklch(lighter)[0], 0.6, places=2)
        self.assertAlmostEqual(to_oklch(darker)[0], 0.4, places=2)
        self.assertAlmostEqual(to_oklch(lighter)[2], to_oklch(base)[2], places=2)

    def test_capsule_is_centred_on_the_point_given(self) -> None:
        from PySide6.QtCore import QPointF

        bounds = shading.capsule(100.0, 50.0, 80.0, 40.0, 10.0, 0.0).boundingRect()
        self.assertAlmostEqual(bounds.center().x(), 100.0, places=3)
        self.assertAlmostEqual(bounds.center().y(), 50.0, places=3)

    def test_capsule_rotates_about_its_own_centre(self) -> None:
        import math

        upright = shading.capsule(100.0, 50.0, 80.0, 40.0, 10.0, 0.0).boundingRect()
        turned = shading.capsule(100.0, 50.0, 80.0, 40.0, 10.0, math.pi / 2).boundingRect()
        self.assertAlmostEqual(turned.center().x(), upright.center().x(), places=3)
        self.assertAlmostEqual(turned.width(), upright.height(), places=3)

    def test_zero_depth_leaves_the_background_flat(self) -> None:
        from PySide6.QtGui import QImage, QPainter

        from corak.palette import Palette

        image = QImage(80, 50, QImage.Format.Format_RGB32)
        painter = QPainter(image)
        shading.underlay(painter, Frame(80, 50), Palette(4), random.Random(1), 0.0)
        painter.end()
        corners = {image.pixelColor(x, y).name() for x in (1, 78) for y in (1, 48)}
        self.assertEqual(len(corners), 1)

    def test_depth_gives_the_background_somewhere_bright(self) -> None:
        from PySide6.QtGui import QImage, QPainter

        from corak.palette import Palette

        image = QImage(80, 50, QImage.Format.Format_RGB32)
        painter = QPainter(image)
        shading.underlay(painter, Frame(80, 50), Palette(4), random.Random(1), 1.0)
        painter.end()
        values = [image.pixelColor(x, y).valueF() for x in (1, 78) for y in (1, 48)]
        self.assertGreater(max(values) - min(values), 0.01)


if __name__ == "__main__":
    unittest.main()
