"""Physical display geometry.

Two sources, because neither is sufficient alone. Qt works anywhere but under
Wayland learns only an integer buffer scale from the compositor, so a 1.5x
output is reported as 2x and its panel looks larger than it is -- and under the
offscreen platform plugin, which is how the headless rotation runs, it sees a
single virtual screen and nothing real at all. KScreen knows the true modes and
needs no display, so on KDE it is preferred and Qt is the fallback.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass

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
    if app is None:
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
    screens = _from_kscreen() or _from_qt()
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
