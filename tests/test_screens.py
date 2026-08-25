"""Display geometry, and the kernel source in particular.

Nothing here reads the running machine: every connector is a directory written
into a temporary tree, so the tests mean the same thing on a laptop, a three
monitor desktop and a runner with no display at all.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

_isolated = tempfile.mkdtemp(prefix="corak-tests-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_isolated, "config")
os.environ["XDG_DATA_HOME"] = os.path.join(_isolated, "data")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from corak.screens import (
    Panel,
    Screen,
    _drm_only,
    merge_drm,
    parse_edid,
    read_drm,
)


def edid(width_mm: int, height_mm: int, *, detailed: bool = True) -> bytes:
    """A block carrying one physical size, the way a monitor reports it."""
    blob = bytearray(128)
    blob[21] = width_mm // 10
    blob[22] = height_mm // 10
    if detailed:
        timing = bytearray(18)
        timing[0] = 0x01  # a non-zero pixel clock marks a detailed timing
        timing[12] = width_mm & 0xFF
        timing[13] = height_mm & 0xFF
        timing[14] = ((width_mm >> 8) << 4) | ((height_mm >> 8) & 0x0F)
        blob[54:72] = timing
    return bytes(blob)


def connector(
    root: Path,
    name: str,
    *,
    card: str = "card1",
    status: str = "connected",
    enabled: str = "enabled",
    modes: str = "3840x1100\n1920x1080\n",
    blob: bytes | None = None,
) -> None:
    directory = root / f"{card}-{name}"
    directory.mkdir(parents=True)
    (directory / "status").write_text(status + "\n")
    (directory / "enabled").write_text(enabled + "\n")
    (directory / "modes").write_text(modes)
    if blob is not None:
        (directory / "edid").write_bytes(blob)


def screen(name: str, width: int, height: int, **kwargs: object) -> Screen:
    fields: dict[str, object] = {
        "name": name,
        "width": width,
        "height": height,
        "x": 0,
        "y": 0,
        "logical_width": width,
        "logical_height": height,
        "primary": False,
    }
    fields.update(kwargs)
    return Screen(**fields)  # type: ignore[arg-type]


class ParseEdid(unittest.TestCase):
    def test_reads_the_detailed_timing(self) -> None:
        self.assertEqual(parse_edid(edid(597, 336)), (597, 336))

    def test_sizes_past_one_metre_survive_the_split_high_bits(self) -> None:
        # Width and height share byte 14, four bits each.
        self.assertEqual(parse_edid(edid(1210, 680)), (1210, 680))

    def test_falls_back_to_the_centimetre_fields(self) -> None:
        self.assertEqual(parse_edid(edid(800, 330, detailed=False)), (800, 330))

    def test_a_short_block_reports_nothing(self) -> None:
        self.assertEqual(parse_edid(b"\x00" * 64), (0, 0))

    def test_no_block_at_all_reports_nothing(self) -> None:
        self.assertEqual(parse_edid(b""), (0, 0))


class ReadDrm(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="corak-drm-"))

    def test_reads_the_native_mode_and_the_physical_size(self) -> None:
        connector(self.root, "HDMI-A-2", blob=edid(597, 336))
        panels = read_drm(self.root)
        self.assertEqual(panels["HDMI-A-2"], Panel("HDMI-A-2", 3840, 1100, 597, 336))

    def test_the_first_mode_wins_over_the_rest(self) -> None:
        connector(self.root, "DP-2", modes="3440x1440\n1920x1080\n800x600\n")
        self.assertEqual(read_drm(self.root)["DP-2"].width, 3440)

    def test_an_interlace_suffix_does_not_defeat_the_parse(self) -> None:
        connector(self.root, "DP-2", modes="1920x1080i\n")
        self.assertEqual(read_drm(self.root)["DP-2"], Panel("DP-2", 1920, 1080, 0, 0))

    def test_a_disconnected_connector_is_skipped(self) -> None:
        connector(self.root, "DP-1", status="disconnected")
        self.assertEqual(read_drm(self.root), {})

    def test_a_connected_but_unused_output_is_skipped(self) -> None:
        connector(self.root, "DP-1", enabled="disabled")
        self.assertEqual(read_drm(self.root), {})

    def test_a_connector_with_no_modes_is_skipped(self) -> None:
        connector(self.root, "DP-1", modes="")
        self.assertEqual(read_drm(self.root), {})

    def test_a_missing_edid_leaves_the_millimetres_at_zero(self) -> None:
        connector(self.root, "DP-2")
        self.assertEqual(read_drm(self.root)["DP-2"].width_mm, 0)

    def test_connectors_on_a_second_card_are_found(self) -> None:
        connector(self.root, "HDMI-A-1", card="card1")
        connector(self.root, "DP-3", card="card2", modes="1920x1080\n")
        self.assertEqual(sorted(read_drm(self.root)), ["DP-3", "HDMI-A-1"])

    def test_a_root_that_is_not_there_reports_nothing(self) -> None:
        self.assertEqual(read_drm(self.root / "absent"), {})


class MergeDrm(unittest.TestCase):
    def test_the_kernel_corrects_qt_s_pixels(self) -> None:
        # Qt reads a 1.5x output as 2x, so 3840x1100 arrives as 5120x1466.
        panels = {"HDMI-A-2": Panel("HDMI-A-2", 3840, 1100, 597, 336)}
        merged = merge_drm(panels, [screen("HDMI-A-2", 5120, 1466, width_mm=597, height_mm=336)])
        self.assertEqual((merged[0].width, merged[0].height), (3840, 1100))

    def test_the_layout_qt_reported_is_kept(self) -> None:
        panels = {"DP-2": Panel("DP-2", 3440, 1440, 797, 334)}
        placed = screen("DP-2", 3440, 1440, x=1080, y=200, logical_width=2293, primary=True)
        merged = merge_drm(panels, [placed])
        self.assertEqual((merged[0].x, merged[0].y), (1080, 200))
        self.assertEqual(merged[0].logical_width, 2293)
        self.assertTrue(merged[0].primary)

    def test_a_turned_panel_takes_the_rotation_with_its_millimetres(self) -> None:
        # The kernel describes the panel unrotated; Qt knows it is on its side.
        panels = {"DP-3": Panel("DP-3", 1920, 1080, 530, 280)}
        merged = merge_drm(panels, [screen("DP-3", 1080, 1920)])
        self.assertEqual((merged[0].width, merged[0].height), (1080, 1920))
        self.assertEqual((merged[0].width_mm, merged[0].height_mm), (280, 530))

    def test_an_upright_panel_keeps_its_millimetres(self) -> None:
        panels = {"DP-2": Panel("DP-2", 3440, 1440, 797, 334)}
        merged = merge_drm(panels, [screen("DP-2", 3440, 1440)])
        self.assertEqual((merged[0].width_mm, merged[0].height_mm), (797, 334))

    def test_a_screen_the_kernel_does_not_know_is_left_alone(self) -> None:
        untouched = screen("VIRTUAL-1", 1280, 720, width_mm=1, height_mm=1)
        self.assertEqual(merge_drm({}, [untouched]), [untouched])


class DrmOnly(unittest.TestCase):
    def test_panels_are_laid_out_left_to_right(self) -> None:
        panels = {
            "DP-2": Panel("DP-2", 3440, 1440, 797, 334),
            "HDMI-A-2": Panel("HDMI-A-2", 3840, 1100, 597, 336),
        }
        first, second = _drm_only(panels)
        self.assertEqual((first.x, second.x), (0, 3440))

    def test_the_first_panel_is_the_primary_one(self) -> None:
        panels = {"DP-2": Panel("DP-2", 3440, 1440, 797, 334)}
        self.assertTrue(_drm_only(panels)[0].primary)

    def test_the_physical_size_is_carried_through(self) -> None:
        panels = {"DP-2": Panel("DP-2", 3440, 1440, 797, 334)}
        built = _drm_only(panels)[0]
        self.assertEqual((built.width_mm, built.height_mm), (797, 334))
        self.assertAlmostEqual(built.px_per_mm, (3440 / 797 + 1440 / 334) / 2, places=3)


if __name__ == "__main__":
    unittest.main()
