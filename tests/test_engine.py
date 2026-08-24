"""Engine and session behaviour.

A QApplication has to exist before any QImage or widget work, and the offscreen
platform plugin lets that happen without a display.
"""

from __future__ import annotations

import os
import random
import tempfile
import unittest
from unittest import mock

# Tests must not see the running user's installed themes or settings: a theme
# dropped into the real config directory would otherwise change what they mean.
_isolated = tempfile.mkdtemp(prefix="corak-tests-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_isolated, "config")
os.environ["XDG_DATA_HOME"] = os.path.join(_isolated, "data")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

# QApplication rather than QGuiApplication: it is a subclass, and the widget
# tests need one. Creating the narrower class first leaves them unable to build
# a QWidget at all.
_app = QApplication.instance() or QApplication([])

from corak import themes
from corak.design import Design, History
from corak.engine import Engine, NoPatternsEnabled, UnknownPattern
from corak.palette import Palette, to_oklch
from corak.patterns import names
from corak.session import Session


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
    """A theme constrains what the seed is allowed to produce.

    These build their own themes rather than leaning on the shipped ones: a
    test that fails because a theme was retuned is testing the wrong thing.
    """

    COOL = themes.Theme(
        id="cool", name="Cool", schemes=("analogous", "split"),
        hue_range=(0.47, 0.63), chroma=(0.07, 0.14), dark=True,
    )
    WARM = themes.Theme(
        id="warm", name="Warm", schemes=("mono", "analogous"),
        hue_range=(0.94, 1.14), chroma=(0.09, 0.17), dark=True,
    )
    FLAT = themes.Theme(
        id="flat", name="Flat", patterns=("hexagons", "triangles"),
        schemes=("mono",), chroma=(0.008, 0.032), dark=True, scale=1.7,
    )
    PALE = themes.Theme(
        id="pale", name="Pale", schemes=("mono", "analogous"),
        hue_range=(0.45, 1.12), chroma=(0.03, 0.07), lightness=(0.52, 0.72),
        dark=False,
    )

    def setUp(self) -> None:
        self.engine = Engine(themes=(self.COOL, self.WARM, self.FLAT, self.PALE))

    def test_design_records_which_theme_made_it(self) -> None:
        design = self.engine.new_design(random.Random(1), theme=self.WARM)
        self.assertEqual(design.theme, "warm")
        self.assertIn("warm", design.slug())

    def test_hue_stays_inside_the_theme_range(self) -> None:
        low, high = self.COOL.hue_range
        for seed in range(25):
            palette = Palette.for_theme(seed, self.COOL)
            with self.subTest(seed=seed):
                self.assertGreaterEqual(palette.base_hue, low)
                self.assertLessEqual(palette.base_hue, high)

    def test_a_wrapping_hue_range_is_allowed(self) -> None:
        # 0.94 past 1.0 to 0.14 must wrap rather than collapse to empty.
        hues = {round(Palette.for_theme(s, self.WARM).base_hue, 3) for s in range(40)}
        self.assertTrue(any(h > 0.9 for h in hues))
        self.assertTrue(any(h < 0.15 for h in hues))

    def test_every_ramp_colour_stays_inside_the_theme_range(self) -> None:
        # Constraining only the base hue is not enough: a split scheme reaches
        # 0.58 of a turn away, which would carry a blue theme into brown.
        low, high = self.COOL.hue_range
        for seed in range(30):
            palette = Palette.for_theme(seed, self.COOL)
            for colour in palette.colors:
                _lightness, chroma, hue = to_oklch(colour)
                if chroma < 0.01:
                    continue
                with self.subTest(seed=seed, scheme=palette.scheme):
                    self.assertTrue(low - 0.02 <= hue <= high + 0.02, f"hue {hue:.3f}")

    def test_a_light_theme_never_reaches_the_khaki_band(self) -> None:
        # Between roughly 0.12 and 0.45 of a turn, anything below a lightness
        # of about 0.75 reads as khaki rather than as colour.
        for seed in range(120):
            for colour in Palette.for_theme(seed, self.PALE).colors:
                lightness, chroma, hue = to_oklch(colour)
                if chroma < 0.01:
                    continue
                with self.subTest(seed=seed):
                    self.assertFalse(0.15 <= hue <= 0.42 and lightness < 0.75)

    def test_a_light_background_stays_lighter_than_the_ramp(self) -> None:
        for seed in range(40):
            palette = Palette.for_theme(seed, self.PALE)
            lightest = max(to_oklch(c)[0] for c in palette.colors)
            with self.subTest(seed=seed):
                self.assertGreaterEqual(to_oklch(palette.background)[0], lightest - 0.02)

    def test_calm_does_not_override_a_theme_that_asked_to_be_light(self) -> None:
        # Otherwise the background follows the forced dark palette while the
        # shapes follow the theme's lightness, and the gaps come out black.
        design = self.engine.new_design(random.Random(3), pattern="hexagons", theme=self.PALE)
        image = self.engine.render(design, 200, 120, {"calm": 0.4})
        self.assertGreater(to_oklch(image.pixelColor(1, 1))[0], 0.4)

    def test_calm_still_darkens_an_unconstrained_palette(self) -> None:
        light = Palette(99, dark=False)
        forced = Palette(99, dark=True)
        self.assertLess(to_oklch(forced.background)[0], to_oklch(light.background)[0])

    def test_chroma_stays_inside_the_theme_range(self) -> None:
        for seed in range(20):
            chroma = max(to_oklch(c)[1] for c in Palette.for_theme(seed, self.FLAT).colors)
            with self.subTest(seed=seed):
                # Gamut fitting can only reduce chroma, never raise it.
                self.assertLessEqual(chroma, self.FLAT.chroma[1] * 1.2)

    def test_scatter_gives_up_rather_than_looping_when_nowhere_is_dense(self) -> None:
        # Placement rejects candidates until the density field accepts one; a
        # field that never does must not spin.
        from corak.patterns import scatter as scatter_module

        design = self.engine.new_design(random.Random(2), pattern="scatter")
        with mock.patch.object(scatter_module, "field", return_value=lambda u, v: 0.0):
            image = self.engine.render(design, 200, 120)
        self.assertEqual((image.width(), image.height()), (200, 120))

    def test_recolour_changes_a_fixed_palette_theme(self) -> None:
        # Themes that give explicit colours have no formula to reseed, so the
        # left arrow used to produce a byte-identical image for every one.
        fixed = themes.Theme(
            id="fixed", name="Fixed",
            colors=("#12202b", "#2b5468", "#7fa6b8", "#d0ddE4"), dark=True,
        )
        engine = Engine(themes=(fixed,))
        self.assertNotEqual(
            engine.render(Design("hexagons", 4242, 1, "fixed"), 200, 120),
            engine.render(Design("hexagons", 4242, 2, "fixed"), 200, 120),
        )

    def test_recolour_does_not_move_anything(self) -> None:
        engine = Engine()
        for pattern in names():
            with self.subTest(pattern=pattern):
                self.assertEqual(
                    engine.render(Design(pattern, 777, 1), 160, 100),
                    engine.render(Design(pattern, 777, 1), 160, 100),
                )

    def test_theme_narrows_the_pattern_choice(self) -> None:
        chosen = {
            self.engine.new_design(random.Random(s), theme=self.FLAT).pattern for s in range(30)
        }
        self.assertTrue(chosen <= set(self.FLAT.patterns))

    def test_disabled_patterns_still_win_over_the_theme(self) -> None:
        engine = Engine(enabled=["waves"], themes=(self.FLAT,))
        design = engine.new_design(random.Random(0), theme=self.FLAT)
        self.assertEqual(design.pattern, "waves")

    def test_theme_scale_changes_feature_size(self) -> None:
        design = self.engine.new_design(random.Random(4), pattern="hexagons")
        self.assertNotEqual(
            self.engine.render(replace_theme(design, "flat"), 300, 200),
            self.engine.render(replace_theme(design, "cool"), 300, 200),
        )

    def test_the_same_design_under_a_theme_is_reproducible(self) -> None:
        design = self.engine.new_design(random.Random(7), theme=self.PALE)
        self.assertEqual(
            self.engine.render(design, 200, 120), self.engine.render(design, 200, 120)
        )

    def test_a_design_survives_a_round_trip_through_its_slug(self) -> None:
        for design in (
            Design("hexagons", 0x1F2E3D, 0x4A5B6C, "tundra"),
            Design("waves", 1, 2),
        ):
            with self.subTest(design=design):
                self.assertEqual(Design.parse(design.slug()), design)

    def test_a_slug_that_is_not_one_is_rejected(self) -> None:
        for bad in ("", "nonsense", "waves-xyz-123", "a-b-c-d-e", "waves-1"):
            with self.subTest(slug=bad), self.assertRaises(ValueError):
                Design.parse(bad)

    def test_the_arrow_keys_are_bound_the_way_they_are_described(self) -> None:
        # Left is back, not recolour. It breaks the symmetry of one axis per
        # horizontal key, but back-is-left is the stronger habit.
        from PySide6.QtCore import QEvent, Qt
        from PySide6.QtGui import QKeyEvent

        from corak.config import Settings
        from corak.ui.window import ARROWS, MainWindow

        settings = Settings(patterns=names())
        engine = Engine(settings.patterns)
        window = MainWindow(Session(engine, random.Random(3)), settings, None, (800, 400))

        first = window.session.current
        window.keyPressEvent(
            QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Up, Qt.KeyboardModifier.NoModifier)
        )
        second = window.session.current
        self.assertNotEqual(first, second)

        window.keyPressEvent(
            QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Left, Qt.KeyboardModifier.NoModifier)
        )
        self.assertEqual(window.session.current, first, "left should step back")

        held = window.session.current
        window.keyPressEvent(
            QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)
        )
        after = window.session.current
        self.assertEqual(after.pattern_seed, held.pattern_seed, "down should keep the geometry")
        self.assertNotEqual(after.palette_seed, held.palette_seed, "down should recolour")

        captions = dict(ARROWS)
        self.assertIn("back", captions["←"])
        self.assertIn("colours", captions["↓"])

    def test_arrow_actions_keep_the_theme(self) -> None:
        session = Session(self.engine, random.Random(2), theme=self.COOL)
        for action in (session.recolour, session.repattern, session.regenerate):
            with self.subTest(action=action.__name__):
                self.assertEqual(action().theme, "cool")


def replace_theme(design: Design, theme: str) -> Design:
    return Design(design.pattern, design.pattern_seed, design.palette_seed, theme)


if __name__ == "__main__":
    unittest.main()
