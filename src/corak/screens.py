"""Physical display geometry.

Qt reports sizes in logical pixels, which on a scaled output is not the panel's
real resolution -- multiplying by the device pixel ratio is what makes "exactly
native" true rather than approximately true. Both are kept: images are rendered
at native size, while desktop shells identify screens by logical position.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, replace

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication


def configure_scaling() -> None:
    """Stop Qt rounding fractional display scales.

    Qt rounds a 1.5x output up to a device pixel ratio of 2, which would have a
    3840x1100 panel reported as 5120x1466 -- so the wallpaper would be rendered
    oversized and then scaled back down. Must be called before the application
    object exists.
    """
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )


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

    @property
    def aspect(self) -> float:
        return self.width / self.height if self.height else 1.0

    @property
    def portrait(self) -> bool:
        return self.height > self.width

    def __str__(self) -> str:
        return f"{self.name} {self.width}x{self.height}"


def _kscreen_native() -> dict[str, tuple[int, int]]:
    """Native pixel sizes straight from KScreen, keyed by output name.

    Qt only learns an integer buffer scale from the Wayland compositor, so a
    1.5x output is reported as 2x and the panel looks larger than it is. KScreen
    knows the real mode, already adjusted for rotation, so where it is present
    its numbers win.
    """
    if shutil.which("kscreen-doctor") is None:
        return {}
    try:
        raw = subprocess.run(
            ["kscreen-doctor", "-j"], capture_output=True, text=True, timeout=10, check=True
        ).stdout
        outputs = json.loads(raw).get("outputs", [])
    except (OSError, subprocess.SubprocessError, ValueError):
        return {}

    sizes = {}
    for output in outputs:
        size = output.get("size") or {}
        if output.get("enabled") and size.get("width") and size.get("height"):
            sizes[output.get("name", "")] = (int(size["width"]), int(size["height"]))
    return sizes


def detect() -> list[Screen]:
    app = QGuiApplication.instance()
    if app is None:
        raise RuntimeError("a QGuiApplication must exist before detecting screens")
    primary = app.primaryScreen()
    found = []
    for screen in app.screens():
        size = screen.size()
        ratio = screen.devicePixelRatio()
        geometry = screen.geometry()
        found.append(
            Screen(
                name=screen.name(),
                width=round(size.width() * ratio),
                height=round(size.height() * ratio),
                x=geometry.x(),
                y=geometry.y(),
                logical_width=geometry.width(),
                logical_height=geometry.height(),
                primary=screen is primary,
            )
        )

    native = _kscreen_native()
    return [
        replace(s, width=native[s.name][0], height=native[s.name][1]) if s.name in native else s
        for s in found
    ]


def primary_size(fallback: tuple[int, int] = (3840, 2160)) -> tuple[int, int]:
    for screen in detect():
        if screen.primary:
            return screen.width, screen.height
    return fallback
