"""Engine and session behaviour.

A QGuiApplication has to exist before any QImage work, and the offscreen
platform plugin lets that happen without a display.
"""

from __future__ import annotations

import os
import random
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402

_app = QGuiApplication.instance() or QGuiApplication([])

from corak.design import Design, History  # noqa: E402
from corak.engine import Engine, NoPatternsEnabled, UnknownPattern  # noqa: E402
from corak.patterns import names  # noqa: E402
from corak.session import Session  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
