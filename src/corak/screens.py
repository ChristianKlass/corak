"""Physical display geometry.

Three sources, because none is sufficient alone. Qt works anywhere but under
Wayland learns only an integer buffer scale from the compositor, so a 1.5x
output is reported as 2x and its panel looks larger than it is -- and under the
offscreen platform plugin, which is how the headless rotation runs, it sees a
single virtual screen and nothing real at all. KScreen knows the true modes and
needs no display, but it is a KDE tool and absent everywhere else.

The kernel knows as well, and tells anyone who asks: every connector under
/sys/class/drm carries its native mode and its EDID. That works with no
compositor, no session bus and no desktop, so it covers the sessions KScreen
does not. It cannot know about rotation, which is the compositor's business,
so Qt supplies the orientation and the layout while the kernel supplies the
pixels and the millimetres.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

from .frame import NOMINAL_PX_PER_MM, Frame


def configure_scaling() -> None:
    """Stop Qt rounding fractional display scales.

    Must be called before the application object exists.
    """
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )


# Beyond this disagreement between the horizontal and vertical densities the
# reported physical size is not describing the mode in use -- some displays
# report the panel while running a cropped or letterboxed mode -- and a nominal
# density is the safer guess.
MAX_DENSITY_SKEW = 1.25


@dataclass(frozen=True)
class Screen:
    name: str
    width: int
    height: int
    x: int
    y: int
    logical_width: int
    logical_height: int
    primary: bool
    width_mm: int = 0
    height_mm: int = 0

    @property
    def px_per_mm(self) -> float:
        """Pixel density, or a nominal one where the reported size is unusable."""
        if not self.width_mm or not self.height_mm:
            return NOMINAL_PX_PER_MM
        horizontal = self.width / self.width_mm
        vertical = self.height / self.height_mm
        if not horizontal or not vertical:
            return NOMINAL_PX_PER_MM
        skew = max(horizontal, vertical) / min(horizontal, vertical)
        if skew > MAX_DENSITY_SKEW:
            return NOMINAL_PX_PER_MM
        return (horizontal + vertical) / 2.0

    @property
    def aspect(self) -> float:
        return self.width / self.height if self.height else 1.0

    @property
    def portrait(self) -> bool:
        return self.height > self.width

    def __str__(self) -> str:
        return f"{self.name} {self.width}x{self.height}"


def parse_kscreen(payload: str) -> list[Screen]:
    """Build screens from `kscreen-doctor -j` output."""
    try:
        outputs = json.loads(payload).get("outputs", [])
    except (ValueError, AttributeError):
        return []

    screens = []
    for output in outputs:
        size = output.get("size") or {}
        width, height = int(size.get("width", 0)), int(size.get("height", 0))
        if not output.get("enabled") or not width or not height:
            continue
        # `size` is already the rotated panel size, so a portrait monitor
        # reports 1080x1920 rather than the 1920x1080 of its mode.
        scale = float(output.get("scale") or 1.0) or 1.0
        position = output.get("pos") or {}
        physical = output.get("sizeMM") or {}
        width_mm, height_mm = int(physical.get("width", 0)), int(physical.get("height", 0))
        # `size` is rotated but `sizeMM` describes the panel, so a quarter turn
        # has to be applied to the physical dimensions as well.
        if output.get("rotation") in (2, 8):
            width_mm, height_mm = height_mm, width_mm
        screens.append(
            Screen(
                name=output.get("name", ""),
                width=width,
                height=height,
                x=int(position.get("x", 0)),
                y=int(position.get("y", 0)),
                logical_width=round(width / scale),
                logical_height=round(height / scale),
                primary=output.get("priority") == 1,
                width_mm=width_mm,
                height_mm=height_mm,
            )
        )
    return screens


DRM_ROOT = Path("/sys/class/drm")

# The kernel lists modes as "3840x1100", sometimes with an interlace suffix.
MODE = re.compile(r"^(\d+)x(\d+)")


@dataclass(frozen=True)
class Panel:
    """One connector as the kernel describes it, before any rotation."""

    name: str
    width: int
    height: int
    width_mm: int = 0
    height_mm: int = 0


def parse_edid(blob: bytes) -> tuple[int, int]:
    """Physical size in millimetres from an EDID block, or zeros."""
    if len(blob) < 128:
        return 0, 0
    # The first detailed timing descriptor carries millimetres. A zero pixel
    # clock means the block is some other descriptor, and only the centimetre
    # fields in the basic parameters are left, which round harder.
    timing = blob[54:72]
    if timing[0] or timing[1]:
        width = timing[12] | ((timing[14] >> 4) << 8)
        height = timing[13] | ((timing[14] & 0x0F) << 8)
        if width and height:
            return width, height
    return blob[21] * 10, blob[22] * 10


def read_drm(root: Path = DRM_ROOT) -> dict[str, Panel]:
    """Native mode and physical size per connected connector."""
    panels: dict[str, Panel] = {}
    try:
        entries = sorted(root.iterdir())
    except OSError:
        return panels

    for entry in entries:
        # Directories are named cardN-CONNECTOR, and the connector half is
        # what every other source calls the screen.
        name = entry.name.partition("-")[2]
        if not name:
            continue
        try:
            if entry.joinpath("status").read_text().strip() != "connected":
                continue
            # A connected but unused output is not part of the desktop.
            enabled = entry.joinpath("enabled")
            if enabled.exists() and enabled.read_text().strip() != "enabled":
                continue
            modes = entry.joinpath("modes").read_text().split()
        except OSError:
            continue

        # The first mode is the preferred one, which is the panel's own
        # resolution rather than whatever it happens to be driven at.
        found = MODE.match(modes[0]) if modes else None
        if found is None:
            continue
        try:
            edid = entry.joinpath("edid").read_bytes()
        except OSError:
            edid = b""
        width_mm, height_mm = parse_edid(edid)
        panels[name] = Panel(
            name=name,
            width=int(found.group(1)),
            height=int(found.group(2)),
            width_mm=width_mm,
            height_mm=height_mm,
        )
    return panels


def merge_drm(panels: Mapping[str, Panel], laid_out: Sequence[Screen]) -> list[Screen]:
    """Correct Qt's pixels and millimetres with the kernel's, keeping its layout."""
    screens: list[Screen] = []
    for screen in laid_out:
        panel = panels.get(screen.name)
        if panel is None:
            screens.append(screen)
            continue
        width, height = panel.width, panel.height
        width_mm, height_mm = panel.width_mm, panel.height_mm
        # The kernel describes the panel and the compositor may have turned it.
        # Qt knows the orientation in use, so a disagreement is a quarter turn
        # and both the pixels and the millimetres follow it.
        if screen.portrait != (height > width):
            width, height = height, width
            width_mm, height_mm = height_mm, width_mm
        screens.append(
            replace(screen, width=width, height=height, width_mm=width_mm, height_mm=height_mm)
        )
    return screens


def _drm_only(panels: Mapping[str, Panel]) -> list[Screen]:
    """Screens from the kernel alone, for a session Qt cannot see.

    Rotation and placement are the compositor's to know, so this lays the
    panels out left to right unrotated. It is the last thing short of guessing.
    """
    screens: list[Screen] = []
    x = 0
    for panel in panels.values():
        screens.append(
            Screen(
                name=panel.name,
                width=panel.width,
                height=panel.height,
                x=x,
                y=0,
                logical_width=panel.width,
                logical_height=panel.height,
                primary=not screens,
                width_mm=panel.width_mm,
                height_mm=panel.height_mm,
            )
        )
        x += panel.width
    return screens


def _from_drm() -> list[Screen]:
    panels = read_drm()
    if not panels:
        return []
    laid_out = _from_qt()
    if any(screen.name in panels for screen in laid_out):
        return merge_drm(panels, laid_out)
    return _drm_only(panels)


def _from_kscreen() -> list[Screen]:
    if shutil.which("kscreen-doctor") is None:
        return []
    # kscreen-doctor is itself a Qt program: inheriting our offscreen platform
    # would leave it unable to reach the compositor, which is exactly the
    # headless case this is here to serve.
    environment = {k: v for k, v in os.environ.items() if k != "QT_QPA_PLATFORM"}
    try:
        done = subprocess.run(
            ["kscreen-doctor", "-j"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return parse_kscreen(done.stdout)


def _from_qt() -> list[Screen]:
    app = QGuiApplication.instance()
    if not isinstance(app, QGuiApplication):
        return []
    primary = app.primaryScreen()
    screens = []
    for screen in app.screens():
        size = screen.size()
        ratio = screen.devicePixelRatio()
        geometry = screen.geometry()
        screens.append(
            Screen(
                name=screen.name(),
                width=round(size.width() * ratio),
                height=round(size.height() * ratio),
                x=geometry.x(),
                y=geometry.y(),
                logical_width=geometry.width(),
                logical_height=geometry.height(),
                primary=screen is primary,
                width_mm=round(screen.physicalSize().width()),
                height_mm=round(screen.physicalSize().height()),
            )
        )
    return screens


def detect() -> list[Screen]:
    screens = _from_kscreen() or _from_drm() or _from_qt()
    if not screens:
        raise RuntimeError("no screens detected")
    if not any(s.primary for s in screens):
        screens[0] = type(screens[0])(**{**screens[0].__dict__, "primary": True})
    return screens


def frame_for(screen: Screen) -> Frame:
    return Frame(screen.width, screen.height, screen.px_per_mm)


def primary_size(fallback: tuple[int, int] = (3840, 2160)) -> tuple[int, int]:
    try:
        screens = detect()
    except RuntimeError:
        return fallback
    for screen in screens:
        if screen.primary:
            return screen.width, screen.height
    return fallback
