"""Physical display geometry.

Qt reports sizes in logical pixels, which on a scaled output is not the panel's
real resolution -- multiplying by the device pixel ratio is what makes the
"exactly native" requirement true rather than approximately true.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QGuiApplication


@dataclass(frozen=True)
class Screen:
    name: str
    width: int
    height: int
    primary: bool

    @property
    def aspect(self) -> float:
        return self.width / self.height if self.height else 1.0


def _native(screen) -> tuple[int, int]:
    size = screen.size()
    ratio = screen.devicePixelRatio()
    return round(size.width() * ratio), round(size.height() * ratio)


def detect() -> list[Screen]:
    app = QGuiApplication.instance()
    if app is None:
        raise RuntimeError("a QGuiApplication must exist before detecting screens")
    primary = app.primaryScreen()
    found = []
    for screen in app.screens():
        w, h = _native(screen)
        found.append(Screen(screen.name(), w, h, screen is primary))
    return found


def primary_size(fallback: tuple[int, int] = (3840, 2160)) -> tuple[int, int]:
    for screen in detect():
        if screen.primary:
            return screen.width, screen.height
    return fallback
