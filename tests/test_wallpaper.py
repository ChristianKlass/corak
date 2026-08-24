"""Desktop detection and the wallpaper backends.

Nothing here touches the running desktop: the backends' only outside contact is
through `_run` and the D-Bus call, and both are replaced.
"""

from __future__ import annotations

import json
import os
import random
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402

_app = QGuiApplication.instance() or QGuiApplication([])

from corak import screens as sc  # noqa: E402
from corak import wallpaper as wp  # noqa: E402
from corak.engine import Engine  # noqa: E402
from corak.screens import Screen  # noqa: E402


def screen(name="DP-1", w=3440, h=1440, x=0, y=0, primary=True) -> Screen:
    return Screen(name, w, h, x, y, w, h, primary)


class TestDetection(unittest.TestCase):
    def test_known_desktops(self) -> None:
        for desktop, expected in [
            ("KDE", "plasma"),
            ("plasma", "plasma"),
            ("ubuntu:GNOME", "gnome"),
            ("X-Cinnamon", "gnome"),
            ("XFCE", "xfce"),
        ]:
            with self.subTest(desktop=desktop):
                self.assertEqual(wp.detect_backend(desktop).name, expected)

    def test_unknown_desktop_names_what_is_supported(self) -> None:
        with self.assertRaises(wp.WallpaperError) as caught:
            wp.detect_backend("aqua")
        self.assertIn("plasma", str(caught.exception))

    def test_current_desktop_reads_the_environment(self) -> None:
        with mock.patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "KDE"}, clear=False):
            self.assertEqual(wp.current_desktop(), "kde")


class TestFiles(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = Engine()
        self.design = self.engine.new_design(random.Random(2), pattern="waves")

    def test_save_writes_a_named_png(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            image = self.engine.render(self.design, 64, 32)
            path = wp.save(image, self.design, screen(name="HDMI-1"), Path(tmp))
            self.assertTrue(path.exists())
            self.assertIn("HDMI-1", path.name)
            self.assertIn(self.design.slug(), path.name)
            self.assertTrue(re.match(r"\d{8}-\d{6}-", path.name))

    def test_prune_keeps_the_newest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for i in range(6):
                path = directory / f"{i}.png"
                path.write_bytes(b"x")
                os.utime(path, (i, i))
            removed = wp.prune(2, directory)
            self.assertEqual(sorted(Path(p).name for p in removed), ["0.png", "1.png", "2.png", "3.png"])
            self.assertEqual(sorted(p.name for p in directory.glob("*.png")), ["4.png", "5.png"])

    def test_prune_ignores_a_missing_directory(self) -> None:
        self.assertEqual(wp.prune(3, Path("/nonexistent/corak-test")), [])


class TestPlasma(unittest.TestCase):
    def setUp(self) -> None:
        self.backend = wp.PlasmaBackend()
        self.targets = [
            wp.Target(screen("DP-2", 3440, 1440, 0, 129, primary=True), Path("/tmp/a.png")),
            wp.Target(screen("DP-3", 1080, 1920, 3440, 0, primary=False), Path("/tmp/b.png")),
        ]

    def test_script_maps_each_screen_position_to_its_own_image(self) -> None:
        script = self.backend._script(self.targets)
        mapping = json.loads(re.search(r"var byPosition = (\{.*?\});", script).group(1))
        self.assertEqual(mapping, {"0,129": "/tmp/a.png", "3440,0": "/tmp/b.png"})
        self.assertIn("org.kde.image", script)
        self.assertIn("reloadConfig", script)

    def test_falls_back_to_one_image_when_scripting_fails(self) -> None:
        with mock.patch.object(
            self.backend, "_evaluate", side_effect=wp.WallpaperError("no bus")
        ), mock.patch.object(self.backend, "_apply_single") as single:
            self.backend.apply(self.targets)
        single.assert_called_once_with(self.targets)

    def test_fallback_uses_the_primary_screen_image(self) -> None:
        with mock.patch.object(wp.shutil, "which", return_value="/usr/bin/plasma-apply-wallpaperimage"), \
             mock.patch.object(wp, "_run", return_value="") as run:
            self.backend._apply_single(self.targets)
        self.assertEqual(run.call_args[0][0][-1], "/tmp/a.png")

    def test_nothing_happens_without_targets(self) -> None:
        with mock.patch.object(self.backend, "_evaluate") as evaluate:
            self.backend.apply([])
        evaluate.assert_not_called()


class TestGnome(unittest.TestCase):
    def test_sets_both_light_and_dark_keys(self) -> None:
        backend = wp.GnomeBackend()
        targets = [wp.Target(screen(), Path("/tmp/a.png"))]
        with mock.patch.object(wp, "_run", return_value="") as run:
            backend.apply(targets)
        keys = [call[0][0][3] for call in run.call_args_list]
        self.assertEqual(keys, ["picture-uri", "picture-uri-dark", "picture-options"])
        self.assertTrue(run.call_args_list[0][0][0][-1].startswith("file://"))

    def test_survives_an_older_gnome_without_the_dark_key(self) -> None:
        backend = wp.GnomeBackend()
        targets = [wp.Target(screen(), Path("/tmp/a.png"))]
        calls = []

        def fake_run(argv):
            calls.append(argv)
            if argv[3] == "picture-uri-dark":
                raise wp.WallpaperError("no such key")
            return ""

        with mock.patch.object(wp, "_run", side_effect=fake_run):
            backend.apply(targets)
        self.assertEqual(len(calls), 3)


class TestXfce(unittest.TestCase):
    def test_each_monitor_property_gets_its_own_image(self) -> None:
        backend = wp.XfceBackend()
        targets = [
            wp.Target(screen("DP-1", primary=True), Path("/tmp/a.png")),
            wp.Target(screen("HDMI-1", primary=False), Path("/tmp/b.png")),
        ]
        listing = (
            "/backdrop/screen0/monitorDP-1/workspace0/last-image\n"
            "/backdrop/screen0/monitorHDMI-1/workspace0/last-image\n"
            "/backdrop/screen0/monitorDP-1/workspace0/image-style\n"
        )
        with mock.patch.object(wp, "_run", side_effect=[listing, "", ""]) as run:
            backend.apply(targets)
        written = {call[0][0][4]: call[0][0][-1] for call in run.call_args_list[1:]}
        self.assertEqual(
            written,
            {
                "/backdrop/screen0/monitorDP-1/workspace0/last-image": "/tmp/a.png",
                "/backdrop/screen0/monitorHDMI-1/workspace0/last-image": "/tmp/b.png",
            },
        )

    def test_no_properties_is_an_error(self) -> None:
        backend = wp.XfceBackend()
        with mock.patch.object(wp, "_run", return_value=""):
            with self.assertRaises(wp.WallpaperError):
                backend.apply([wp.Target(screen(), Path("/tmp/a.png"))])


class TestRenderAndApply(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = Engine()
        self.design = self.engine.new_design(random.Random(6), pattern="waves")

    def test_renders_one_image_per_screen_at_native_size(self) -> None:
        screens = [screen("A", 800, 400, 0, 0, True), screen("B", 400, 800, 800, 0, False)]
        applied: list = []

        class Fake(wp.Backend):
            name, per_screen = "fake", True

            def apply(self, targets):
                applied.extend(targets)

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            wp, "output_dir", return_value=Path(tmp)
        ):
            targets = wp.render_and_apply(
                self.engine, self.design, screens=screens, backend=Fake(), keep=99
            )
            sizes = [(t.path.exists(), t.screen.width, t.screen.height) for t in targets]
        self.assertEqual(sizes, [(True, 800, 400), (True, 400, 800)])
        self.assertEqual(len(applied), 2)

    def test_single_image_backends_render_only_the_primary(self) -> None:
        screens = [screen("A", 800, 400, 0, 0, False), screen("B", 400, 800, 800, 0, True)]

        class Fake(wp.Backend):
            name, per_screen = "fake", False

            def apply(self, targets):
                pass

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            wp, "output_dir", return_value=Path(tmp)
        ):
            targets = wp.render_and_apply(
                self.engine, self.design, screens=screens, backend=Fake(), keep=99
            )
        self.assertEqual([t.screen.name for t in targets], ["B"])

    def test_unusable_backend_is_reported(self) -> None:
        class Fake(wp.Backend):
            name = "fake"

            def available(self):
                return False

        with self.assertRaises(wp.WallpaperError):
            wp.render_and_apply(self.engine, self.design, screens=[screen()], backend=Fake())


class TestKScreen(unittest.TestCase):
    """Screen geometry comes from KScreen, which Qt cannot supply headless."""

    PAYLOAD = json.dumps(
        {
            "outputs": [
                # A 1.5x output: the panel is 3840x1100 and the desktop 2560x733.
                {
                    "name": "HDMI-1", "enabled": True, "priority": 2, "scale": 1.5,
                    "pos": {"x": 2657, "y": 1920}, "size": {"width": 3840, "height": 1100},
                },
                # Rotated: `size` is already the portrait orientation.
                {
                    "name": "DP-3", "enabled": True, "priority": 1, "scale": 1,
                    "pos": {"x": 3440, "y": 0}, "size": {"width": 1080, "height": 1920},
                },
                {
                    "name": "DP-9", "enabled": False, "priority": 3, "scale": 1,
                    "pos": {"x": 0, "y": 0}, "size": {"width": 1920, "height": 1080},
                },
            ]
        }
    )

    def test_fractional_scale_does_not_inflate_the_panel_size(self) -> None:
        hdmi = next(s for s in sc.parse_kscreen(self.PAYLOAD) if s.name == "HDMI-1")
        self.assertEqual((hdmi.width, hdmi.height), (3840, 1100))
        self.assertEqual((hdmi.logical_width, hdmi.logical_height), (2560, 733))

    def test_rotated_output_is_portrait(self) -> None:
        dp3 = next(s for s in sc.parse_kscreen(self.PAYLOAD) if s.name == "DP-3")
        self.assertTrue(dp3.portrait)
        self.assertEqual((dp3.width, dp3.height), (1080, 1920))

    def test_priority_one_is_the_primary(self) -> None:
        primary = [s.name for s in sc.parse_kscreen(self.PAYLOAD) if s.primary]
        self.assertEqual(primary, ["DP-3"])

    def test_disabled_outputs_are_skipped(self) -> None:
        self.assertNotIn("DP-9", [s.name for s in sc.parse_kscreen(self.PAYLOAD)])

    def test_unparseable_output_is_not_an_error(self) -> None:
        self.assertEqual(sc.parse_kscreen("not json"), [])

    def test_missing_tool_falls_through_to_qt(self) -> None:
        with mock.patch.object(sc.shutil, "which", return_value=None):
            self.assertEqual(sc._from_kscreen(), [])

    def test_the_offscreen_platform_is_not_passed_to_kscreen(self) -> None:
        # kscreen-doctor is itself a Qt program; inheriting the offscreen plugin
        # would leave it unable to reach the compositor.
        captured = {}

        def fake_run(argv, **kwargs):
            captured.update(kwargs.get("env") or {})
            return mock.Mock(stdout=self.PAYLOAD)

        with mock.patch.object(sc.shutil, "which", return_value="/usr/bin/kscreen-doctor"), \
             mock.patch.dict(os.environ, {"QT_QPA_PLATFORM": "offscreen"}, clear=False), \
             mock.patch.object(sc.subprocess, "run", side_effect=fake_run):
            sc._from_kscreen()
        self.assertNotIn("QT_QPA_PLATFORM", captured)


if __name__ == "__main__":
    unittest.main()
