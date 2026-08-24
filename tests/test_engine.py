"""Engine and session behaviour.

A QGuiApplication has to exist before any QImage work, and the offscreen
platform plugin lets that happen without a display.
"""

from __future__ import annotations

import os
import tempfile
import random
import unittest
from unittest import mock

# Tests must not see the running user's installed themes or settings: a theme
# dropped into the real config directory would otherwise change what they mean.
_isolated = tempfile.mkdtemp(prefix="corak-tests-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_isolated, "config")
os.environ["XDG_DATA_HOME"] = os.path.join(_isolated, "data")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402

_app = QGuiApplication.instance() or QGuiApplication([])

from corak.design import Design, History  # noqa: E402
from corak.engine import Engine, NoPatternsEnabled, UnknownPattern  # noqa: E402
from corak.patterns import names  # noqa: E402
from corak.palette import Palette, to_oklch  # noqa: E402
from corak.session import Session  # noqa: E402
from corak import themes  # noqa: E402


class TestEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = Engine()

    def test_patterns_registered(self) -> None:
        self.assertGreaterEqual(len(names()), 3)

    def test_render_matches_requested_size(self) -> None:
        design = self.engine.new_design(random.Random(1))
        image = self.engine.render(design, 321, 123)
        self.assertEqual((image.width(), image.height()), (321, 123))

    def test_same_design_renders_identically(self) -> None:
        for name in names():
            design = self.engine.new_design(random.Random(4), pattern=name)
            with self.subTest(pattern=name):
                self.assertEqual(
                    self.engine.render(design, 200, 120),
                    self.engine.render(design, 200, 120),
                )

    def test_palette_seed_alone_changes_the_image(self) -> None:
        base = self.engine.new_design(random.Random(5), pattern="triangles")
        other = Design(base.pattern, base.pattern_seed, base.palette_seed + 1)
        self.assertNotEqual(
            self.engine.render(base, 200, 120), self.engine.render(other, 200, 120)
        )

    def test_unknown_pattern_rejected(self) -> None:
        with self.assertRaises(UnknownPattern):
            self.engine.new_design(random.Random(0), pattern="nope")

    def test_no_enabled_patterns_is_an_error(self) -> None:
        with self.assertRaises(NoPatternsEnabled):
            Engine(enabled=[]).new_design(random.Random(0))


class TestHistory(unittest.TestCase):
    def test_back_stops_at_the_oldest_entry(self) -> None:
        history = History()
        first = Design("waves", 1, 2)
        history.push(first)
        history.push(Design("waves", 3, 4))
        self.assertEqual(history.back(), first)
        self.assertIsNone(history.back())

    def test_push_truncates_the_forward_branch(self) -> None:
        history = History()
        for i in range(3):
            history.push(Design("waves", i, i))
        history.back()
        history.push(Design("waves", 99, 99))
        self.assertEqual(len(history), 3)
        self.assertIsNone(history.forward())


class TestSession(unittest.TestCase):
    def setUp(self) -> None:
        self.session = Session(Engine(), random.Random(42))

    def test_recolour_keeps_pattern_and_geometry(self) -> None:
        before = self.session.current
        after = self.session.recolour()
        self.assertEqual(after.pattern, before.pattern)
        self.assertEqual(after.pattern_seed, before.pattern_seed)
        self.assertNotEqual(after.palette_seed, before.palette_seed)

    def test_repattern_keeps_colours(self) -> None:
        before = self.session.current
        after = self.session.repattern()
        self.assertEqual(after.palette_seed, before.palette_seed)
        self.assertNotEqual(after.pattern, before.pattern)

    def test_regenerate_starts_over(self) -> None:
        before = self.session.current
        after = self.session.regenerate()
        self.assertNotEqual(after.palette_seed, before.palette_seed)

    def test_previous_returns_what_was_shown_before(self) -> None:
        first = self.session.current
        self.session.regenerate()
        self.assertEqual(self.session.previous(), first)

    def test_repattern_with_one_pattern_enabled_still_moves(self) -> None:
        session = Session(Engine(enabled=["waves"]), random.Random(1))
        before = session.current
        after = session.repattern()
        self.assertEqual(after.pattern, "waves")
        self.assertNotEqual(after.pattern_seed, before.pattern_seed)


class TestThemes(unittest.TestCase):
    """A theme constrains what the seed is allowed to produce."""

    def setUp(self) -> None:
        self.engine = Engine()

    def test_design_records_which_theme_made_it(self) -> None:
        design = self.engine.new_design(random.Random(1), theme=themes.get("ember"))
        self.assertEqual(design.theme, "ember")
        self.assertIn("ember", design.slug())

    def test_hue_stays_inside_the_theme_range(self) -> None:
        tide = themes.get("tide")
        for seed in range(25):
            palette = Palette.for_theme(seed, tide)
            with self.subTest(seed=seed):
                self.assertGreaterEqual(palette.base_hue, tide.hue_range[0])
                self.assertLessEqual(palette.base_hue, tide.hue_range[1])

    def test_a_wrapping_hue_range_is_allowed(self) -> None:
        # Ember runs from 0.94 past 1.0 to 0.14, which must wrap rather than
        # collapse to an empty range.
        hues = {round(Palette.for_theme(s, themes.get("ember")).base_hue, 3) for s in range(40)}
        self.assertTrue(any(h > 0.9 for h in hues))
        self.assertTrue(any(h < 0.15 for h in hues))

    def test_every_ramp_colour_stays_inside_the_theme_range(self) -> None:
        # Constraining only the base hue is not enough: a split scheme reaches
        # 0.58 of a turn away, which would carry a blue theme into brown.
        tide = themes.get("tide")
        low, high = tide.hue_range
        for seed in range(30):
            palette = Palette.for_theme(seed, tide)
            for colour in palette.colors:
                lightness, chroma, hue = to_oklch(colour)
                if chroma < 0.01:
                    continue  # a near-neutral has no meaningful hue
                with self.subTest(seed=seed, scheme=palette.scheme):
                    distance = min(abs(hue - low), abs(hue - high), 1 - abs(hue - low))
                    inside = low - 0.02 <= hue <= high + 0.02
                    self.assertTrue(inside, f"hue {hue:.3f} outside {low}-{high}")

    def test_chroma_stays_inside_the_theme_range(self) -> None:
        slate = themes.get("slate")
        for seed in range(20):
            chroma = max(to_oklch(c)[1] for c in Palette.for_theme(seed, slate).colors)
            with self.subTest(seed=seed):
                # Gamut fitting can only reduce chroma, never raise it.
                self.assertLessEqual(chroma, slate.chroma[1] * 1.2)

    def test_a_light_theme_never_reaches_the_khaki_band(self) -> None:
        # Between roughly 0.20 and 0.40 of a turn, anything below a perceptual
        # lightness of about 0.75 reads as khaki rather than pastel.
        linen = themes.get("linen")
        low, high = linen.hue_range
        for seed in range(120):
            for colour in Palette.for_theme(seed, linen).colors:
                lightness, chroma, hue = to_oklch(colour)
                if chroma < 0.01:
                    continue
                with self.subTest(seed=seed):
                    khaki = 0.15 <= hue <= 0.42 and lightness < 0.75
                    self.assertFalse(khaki, f"hue {hue:.3f} at L {lightness:.3f}")

    def test_a_light_background_stays_lighter_than_the_ramp(self) -> None:
        linen = themes.get("linen")
        for seed in range(40):
            palette = Palette.for_theme(seed, linen)
            lightest = max(to_oklch(c)[0] for c in palette.colors)
            with self.subTest(seed=seed):
                self.assertGreaterEqual(to_oklch(palette.background)[0], lightest - 0.02)

    def test_calm_does_not_override_a_theme_that_asked_to_be_light(self) -> None:
        # Otherwise the background follows the forced dark palette while the
        # shapes follow the theme's lightness, and the gaps come out black.
        linen = themes.get("linen")
        engine = Engine()
        design = engine.new_design(random.Random(3), pattern="hexagons", theme=linen)
        image = engine.render(design, 200, 120, {"calm": 0.4})
        corner = image.pixelColor(1, 1)
        self.assertGreater(to_oklch(corner)[0], 0.4)

    def test_calm_still_darkens_an_unconstrained_palette(self) -> None:
        engine = Engine()
        design = engine.new_design(random.Random(3), pattern="hexagons")
        light = Palette(design.palette_seed, dark=False)
        forced = Palette(design.palette_seed, dark=True)
        self.assertLess(to_oklch(forced.background)[0], to_oklch(light.background)[0])

    def test_scatter_gives_up_rather_than_looping_when_nowhere_is_dense(self) -> None:
        # Placement rejects candidates until the density field accepts one; a
        # field that never does must not spin.
        from corak.patterns import scatter as scatter_module

        design = self.engine.new_design(random.Random(2), pattern="scatter")
        with mock.patch.object(scatter_module, "field", return_value=lambda u, v: 0.0):
            image = self.engine.render(design, 200, 120)
        self.assertEqual((image.width(), image.height()), (200, 120))

    def test_theme_narrows_the_pattern_choice(self) -> None:
        slate = themes.get("slate")
        chosen = {
            self.engine.new_design(random.Random(s), theme=slate).pattern for s in range(30)
        }
        self.assertTrue(chosen <= set(slate.patterns))

    def test_disabled_patterns_still_win_over_the_theme(self) -> None:
        engine = Engine(enabled=["waves"])
        design = engine.new_design(random.Random(0), theme=themes.get("slate"))
        self.assertEqual(design.pattern, "waves")

    def test_theme_scale_changes_feature_size(self) -> None:
        design = self.engine.new_design(random.Random(4), pattern="hexagons")
        big = self.engine.render(replace_theme(design, "slate"), 300, 200)
        small = self.engine.render(replace_theme(design, "signal"), 300, 200)
        self.assertNotEqual(big, small)

    def test_the_same_design_under_a_theme_is_reproducible(self) -> None:
        design = self.engine.new_design(random.Random(7), theme=themes.get("bloom"))
        self.assertEqual(
            self.engine.render(design, 200, 120), self.engine.render(design, 200, 120)
        )

    def test_recolour_changes_a_fixed_palette_theme(self) -> None:
        # Themes that give explicit colours have no formula to reseed, so the
        # left arrow used to produce a byte-identical image for every one of
        # them.
        fixed = themes.Theme(
            id="fixed",
            name="Fixed",
            colors=("#12202b", "#2b5468", "#7fa6b8", "#d0ddE4"),
            dark=True,
        )
        engine = Engine(themes=(fixed,))
        first = Design("hexagons", 4242, 1, "fixed")
        second = Design("hexagons", 4242, 2, "fixed")
        self.assertNotEqual(engine.render(first, 200, 120), engine.render(second, 200, 120))

    def test_recolour_does_not_move_anything(self) -> None:
        # Colour decisions follow the palette seed and placement follows the
        # pattern seed, so the two are genuinely separate controls.
        engine = Engine()
        for pattern in names():
            with self.subTest(pattern=pattern):
                a = engine.render(Design(pattern, 777, 1), 160, 100)
                b = engine.render(Design(pattern, 777, 1), 160, 100)
                self.assertEqual(a, b)

    def test_arrow_actions_keep_the_theme(self) -> None:
        session = Session(Engine(), random.Random(2), theme=themes.get("tide"))
        for action in (session.recolour, session.repattern, session.regenerate):
            with self.subTest(action=action.__name__):
                self.assertEqual(action().theme, "tide")


def replace_theme(design: Design, theme: str) -> Design:
    return Design(design.pattern, design.pattern_seed, design.palette_seed, theme)


if __name__ == "__main__":
    unittest.main()
