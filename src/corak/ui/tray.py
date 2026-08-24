"""System tray icon.

The icon is a small render of the generator's own output, so it changes with
each rotation rather than being a fixed glyph.
"""

from __future__ import annotations

import random

from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from ..design import Design
from ..engine import Engine

ICON_SIZE = 128


def design_icon(engine: Engine, design: Design) -> QIcon:
    return QIcon(QPixmap.fromImage(engine.render(design, ICON_SIZE, ICON_SIZE)))


class Tray(QSystemTrayIcon):
    def __init__(self, engine: Engine, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._engine = engine
        self.setIcon(design_icon(engine, engine.new_design(random.Random(1))))

        self.menu = QMenu()
        self.action_next = self.menu.addAction("Next wallpaper")
        self.action_show = self.menu.addAction("Show window")
        self.menu.addSeparator()
        self.action_settings = self.menu.addAction("Settings...")
        self.menu.addSeparator()
        self.action_quit = self.menu.addAction("Quit")
        self.setContextMenu(self.menu)

    def show_design(self, design: Design) -> None:
        self.setIcon(design_icon(self._engine, design))
        self.setToolTip(f"corak - {design}")
