"""Settings, history and the schedule."""

from __future__ import annotations

import json
import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402

_app = QGuiApplication.instance() or QGuiApplication([])

from corak import desktop  # noqa: E402
from corak import scheduler  # noqa: E402
from corak import themes  # noqa: E402
from corak.themes import Theme  # noqa: E402
from corak.config import Settings, load, save  # noqa: E402
from corak.engine import Engine  # noqa: E402
from corak.patterns import names  # noqa: E402
from corak.store import Store  # noqa: E402
from corak import wallpaper as wp  # noqa: E402
from corak.config import Settings as _S  # noqa: E402,F401
from corak import rotation  # noqa: E402
from corak.wallpaper import Target  # noqa: E402

from test_wallpaper import screen  # noqa: E402


class TestSettings(unittest.TestCase):
    def test_round_trip(self) -> None:
        original = Settings(interval_minutes=45, patterns=["waves"], theme="tide", keep=3)
        with tempfile.TemporaryDirectory() as tmp:
            path = save(original, Path(tmp) / "settings.json")
            self.assertEqual(load(path), original.normalised())

    def test_missing_file_gives_defaults(self) -> None:
        self.assertEqual(load(Path("/nonexistent/corak/settings.json")), Settings())

    def test_corrupt_file_gives_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text("{ this is not json")
            self.assertEqual(load(path), Settings())

    def test_unknown_keys_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text(json.dumps({"interval_minutes": 12, "from_the_future": True}))
            self.assertEqual(load(path).interval_minutes, 12)

    def test_empty_pattern_list_falls_back_to_everything(self) -> None:
        self.assertEqual(Settings(patterns=[]).normalised().patterns, names())

    def test_patterns_that_no_longer_exist_are_dropped(self) -> None:
        self.assertEqual(Settings(patterns=["waves", "gone"]).normalised().patterns, ["waves"])

    def test_interval_is_clamped(self) -> None:
        self.assertEqual(Settings(interval_minutes=0).normalised().interval_minutes, 1)
        self.assertEqual(Settings(interval_minutes=10**6).normalised().interval_minutes, 24 * 60)

    def test_effect_strengths_are_clamped_and_zeroes_dropped(self) -> None:
        theme = Theme.from_dict(
            {"id": "x", "name": "X", "effects": {"calm": 5.0, "grain": 0.0, "darken": -1}}
        )
        self.assertEqual(theme.effects, {"calm": 1.0})

    def test_a_deleted_theme_falls_back_rather_than_failing(self) -> None:
        self.assertEqual(Settings(theme="gone").normalised().theme, "quiet")

    def test_derived_themes_survive_a_round_trip(self) -> None:
        derived = themes.get("tide").derive(effects={"calm": 0.2}, scale=1.4)
        stored = Settings().with_theme(derived).normalised()
        with tempfile.TemporaryDirectory() as tmp:
            path = save(stored, Path(tmp) / "settings.json")
            loaded = load(path)
        self.assertEqual(loaded.theme, derived.id)
        self.assertEqual(loaded.active_theme(), derived)
        self.assertEqual(loaded.active_theme().derived_from, "tide")

    def test_a_corrupt_custom_theme_is_skipped_not_fatal(self) -> None:
        settings = Settings(custom_themes=[{"id": "bad", "name": "B", "chroma": "nonsense"}])
        self.assertEqual(settings.themes(), [])

    def test_deriving_twice_keeps_pointing_at_the_original(self) -> None:
        once = themes.get("ember").derive(scale=1.1)
        twice = once.derive(scale=1.2)
        self.assertEqual(twice.derived_from, "ember")

    def test_a_derived_theme_replaces_its_namesake(self) -> None:
        first = themes.get("bloom").derive(scale=1.1)
        second = themes.get("bloom").derive(scale=1.9)
        settings = Settings().with_theme(first).with_theme(second)
        self.assertEqual(len(settings.custom_themes), 1)
        self.assertEqual(settings.active_theme().scale, 1.9)

    def test_choosing_a_built_in_does_not_store_a_copy(self) -> None:
        settings = Settings().with_theme(themes.get("tide"))
        self.assertEqual(settings.custom_themes, [])
        self.assertEqual(settings.theme, "tide")

    def test_a_partial_write_cannot_replace_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = save(Settings(interval_minutes=17), Path(tmp) / "settings.json")
            with mock.patch.object(Path, "replace", side_effect=OSError("full")):
                with self.assertRaises(OSError):
                    save(Settings(interval_minutes=99), path)
            self.assertEqual(load(path).interval_minutes, 17)


class TestStore(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "history.db")
        self.engine = Engine()
        self.design = self.engine.new_design(random.Random(3), pattern="waves")

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def _targets(self):
        return [
            Target(screen("DP-1", 3440, 1440), Path("/tmp/a.png")),
            Target(screen("DP-2", 1080, 1920, primary=False), Path("/tmp/b.png")),
        ]

    def test_one_row_per_screen(self) -> None:
        self.assertEqual(self.store.record(self.design, "triad", {"calm": 0.7}, self._targets()), 2)
        self.assertEqual(self.store.count(), 2)

    def test_a_row_reproduces_the_design(self) -> None:
        self.store.record(self.design, "mono", {"grain": 0.4}, self._targets()[:1])
        entry = self.store.recent(1)[0]
        self.assertEqual(entry.design, self.design)
        self.assertEqual(entry.effects, {"grain": 0.4})
        self.assertEqual(entry.scheme, "mono")
        self.assertEqual(
            self.engine.render(entry.design, 120, 80), self.engine.render(self.design, 120, 80)
        )

    def test_recent_is_newest_first(self) -> None:
        for i in range(3):
            other = self.engine.new_design(random.Random(i), pattern="waves")
            self.store.record(other, "mono", {}, self._targets()[:1])
        recent = self.store.recent(2)
        self.assertEqual(len(recent), 2)
        self.assertEqual(recent[0].design.pattern_seed, other.pattern_seed)

    def test_reopening_keeps_the_rows(self) -> None:
        self.store.record(self.design, "mono", {}, self._targets()[:1])
        path = self.store.path
        self.store.close()
        with Store(path) as reopened:
            self.assertEqual(reopened.count(), 1)

    def test_forget_removes_named_images(self) -> None:
        self.store.record(self.design, "mono", {}, self._targets())
        self.store.forget(["/tmp/a.png"])
        self.assertEqual([e.path for e in self.store.recent(9)], ["/tmp/b.png"])


class TestRotationHousekeeping(unittest.TestCase):
    """Pruned images must take their history rows with them."""

    def test_rotate_forgets_rows_for_images_it_deleted(self) -> None:
        store = mock.Mock()
        with mock.patch.object(rotation, "render_and_apply", return_value=[]), \
             mock.patch.object(rotation, "prune", return_value=["/gone/a.png"]):
            rotation.rotate(Settings(patterns=["waves"]), store=store)
        store.forget.assert_called_once_with(["/gone/a.png"])

    def test_nothing_is_forgotten_when_nothing_was_deleted(self) -> None:
        store = mock.Mock()
        with mock.patch.object(rotation, "render_and_apply", return_value=[]), \
             mock.patch.object(rotation, "prune", return_value=[]):
            rotation.rotate(Settings(patterns=["waves"]), store=store)
        store.forget.assert_not_called()

    def test_prune_never_deletes_the_images_just_applied(self) -> None:
        # keep=1 with three screens must still leave all three in place.
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for i in range(5):
                (directory / f"{i}.png").write_bytes(b"x")
                os.utime(directory / f"{i}.png", (i, i))
            kept = len(list(directory.glob("*.png"))) - len(wp.prune(max(1, 3), directory))
        self.assertEqual(kept, 3)


class TestScheduler(unittest.TestCase):
    def test_units_name_the_headless_command(self) -> None:
        with mock.patch.object(scheduler, "executable", return_value="/opt/corak"):
            self.assertIn("ExecStart=/opt/corak --next", scheduler.service_text())

    def test_timer_uses_the_requested_interval(self) -> None:
        self.assertIn("OnUnitActiveSec=45min", scheduler.timer_text(45))

    def test_timer_does_not_catch_up_on_missed_runs(self) -> None:
        # Persistent=true would fire a burst of rotations at login.
        self.assertIn("Persistent=false", scheduler.timer_text(30))

    def test_install_writes_both_units_and_reloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            scheduler, "unit_dir", return_value=Path(tmp)
        ), mock.patch.object(scheduler, "systemctl", return_value="") as run:
            scheduler.install(30)
            written = sorted(p.name for p in Path(tmp).iterdir())
        self.assertEqual(written, ["corak.service", "corak.timer"])
        run.assert_called_once_with("daemon-reload")

    def test_enable_turns_the_timer_on(self) -> None:
        with mock.patch.object(scheduler, "install") as install, mock.patch.object(
            scheduler, "systemctl", return_value=""
        ) as run:
            scheduler.enable(15)
        install.assert_called_once_with(15)
        run.assert_called_once_with("enable", "--now", "corak.timer")

    def test_missing_systemctl_is_reported(self) -> None:
        with mock.patch.object(scheduler.shutil, "which", return_value=None):
            with self.assertRaises(scheduler.SchedulerError):
                scheduler.systemctl("daemon-reload")


class TestDesktopEntry(unittest.TestCase):
    def test_entry_points_at_the_given_executable(self) -> None:
        text = desktop.entry_text("/opt/corak/.venv/bin/corak")
        self.assertIn("Exec=/opt/corak/.venv/bin/corak", text)
        self.assertIn("Icon=corak", text)
        self.assertIn("Type=Application", text)

    def test_icon_is_square_and_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = desktop.write_icon(Path(tmp) / "a.png")
            second = desktop.write_icon(Path(tmp) / "b.png")
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_install_writes_both_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ, {"XDG_DATA_HOME": tmp}, clear=False
        ), mock.patch.object(desktop.shutil, "which", return_value=None):
            icon, entry = desktop.install("/opt/corak")
        self.assertTrue(str(icon).startswith(tmp))
        self.assertTrue(str(entry).endswith("applications/corak.desktop"))


if __name__ == "__main__":
    unittest.main()
