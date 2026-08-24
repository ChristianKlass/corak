"""Main window: shows the current design and owns the key bindings."""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent, QKeyEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from .. import effects as fx
from .. import scheduler
from dataclasses import replace

from ..config import Settings, save
from ..design import Design
from ..rotation import describe, rotate
from ..screens import primary_size
from ..session import Session
from ..store import Store
from ..themes import all_themes
from ..wallpaper import WallpaperError
from .preview import PreviewWidget
from .settings import SettingsDialog

# Rendering the full panel resolution on every keypress is affordable for the
# patterns that exist today, but the preview keeps the target aspect and caps
# the pixel count so a heavier pattern cannot stall the window.
PREVIEW_LONG_EDGE = 1600

EFFECT_KEYS = {
    Qt.Key.Key_C: "calm",
    Qt.Key.Key_D: "darken",
    Qt.Key.Key_V: "vignette",
    Qt.Key.Key_G: "grain",
}


class MainWindow(QMainWindow):
    design_changed = Signal(Design)

    def __init__(
        self,
        session: Session,
        settings: Settings,
        store: Store | None = None,
        target: tuple[int, int] | None = None,
    ) -> None:
        super().__init__()
        self.session = session
        self.settings = settings
        self.store = store
        self.target = target or primary_size()
        self.effects = dict(settings.active_theme().effects)
        self._warning = ""

        self.setWindowTitle("corak")
        self.preview = PreviewWidget(self)

        self.settings_button = QPushButton("Settings...", self)
        self.settings_button.clicked.connect(self.open_settings)
        self.apply_button = QPushButton("Set as wallpaper", self)
        self.apply_button.setDefault(True)
        self.apply_button.clicked.connect(self.apply_wallpaper)
        for button in (self.settings_button, self.apply_button):
            # Focus stays on the window so the arrow keys keep working after a
            # button has been clicked.
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        buttons = QHBoxLayout()
        buttons.addWidget(self.settings_button)
        buttons.addStretch(1)
        buttons.addWidget(self.apply_button)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 8, 8)
        layout.setSpacing(8)
        layout.addWidget(self.preview, 1)
        layout.addLayout(buttons)

        central = QWidget(self)
        central.setLayout(layout)
        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar(self))
        self.resize(1100, 640)

        self._show(session.current)

    def _preview_size(self) -> tuple[int, int]:
        w, h = self.target
        scale = min(1.0, PREVIEW_LONG_EDGE / max(w, h))
        return max(1, round(w * scale)), max(1, round(h * scale))

    def _show(self, design: Design | None) -> None:
        if design is None:
            self.statusBar().showMessage("nothing further back in history", 2000)
            return
        w, h = self._preview_size()
        started = time.perf_counter()
        image = self.session.engine.render(design, w, h, self.effects)
        elapsed = (time.perf_counter() - started) * 1000.0
        self.preview.set_image(image)

        active = ", ".join(f"{k} {v:g}" for k, v in sorted(self.effects.items()))
        self.statusBar().showMessage(
            f"{design}   target {self.target[0]}x{self.target[1]}"
            f"   preview {w}x{h}   {elapsed:.0f} ms"
            + (f"   [{active}]" if active else "")
            + (f"   !  {self._warning}" if self._warning else "")
        )
        self.setWindowTitle(f"corak - {self.settings.active_theme().name}")
        self.design_changed.emit(design)

    def apply_wallpaper(self) -> None:
        design = self.session.current
        self.statusBar().showMessage(f"rendering {design} at native size...")
        self.apply_button.setEnabled(False)
        try:
            _, targets = rotate(
                self.settings,
                self.session.engine,
                self.store,
                design=design,
                effects=self.effects,
            )
        except WallpaperError as exc:
            self.statusBar().showMessage(f"could not set wallpaper: {exc}", 8000)
        else:
            self.statusBar().showMessage(describe(design, targets), 6000)
        finally:
            self.apply_button.setEnabled(True)

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() != SettingsDialog.DialogCode.Accepted:
            return
        self.settings = dialog.result_settings()
        save(self.settings)
        theme = self.settings.active_theme()
        self.session.engine.enabled = list(self.settings.patterns)
        self.session.engine.themes = tuple(self.settings.themes())
        self.effects = dict(theme.effects)
        self._apply_schedule()
        self._show(self.session.set_theme(theme))
        return
    def cycle_theme(self, step: int = 1) -> None:
        """Move to the next theme and generate under it."""
        themes = all_themes(self.settings.themes())
        current = self.settings.active_theme()
        index = next((i for i, t in enumerate(themes) if t.id == current.id), 0)
        theme = themes[(index + step) % len(themes)]
        self.settings = replace(self.settings, theme=theme.id)
        self.effects = dict(theme.effects)
        self._warning = ""
        self._show(self.session.set_theme(theme))

    def _apply_schedule(self) -> None:
        try:
            if self.settings.rotate:
                scheduler.enable(self.settings.interval_minutes)
            else:
                scheduler.disable()
        except scheduler.SchedulerError as exc:
            self.statusBar().showMessage(f"could not change the schedule: {exc}", 8000)

    def _toggle(self, name: str) -> None:
        if name in self.effects:
            del self.effects[name]
            self._warning = ""
        else:
            self.effects[name] = 0.7 if name == "calm" else 0.6
            self._warning = fx.warning(name) or ""
        self._show(self.session.current)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt naming)
        # Hiding rather than quitting keeps the tray icon usable; the tray's
        # Quit action is what actually ends the process.
        if self.isVisible() and QSystemTrayAvailable():
            event.ignore()
            self.hide()
            return
        super().closeEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (Qt naming)
        key = event.key()
        if key == Qt.Key.Key_Up:
            self._show(self.session.regenerate())
        elif key == Qt.Key.Key_Left:
            self._show(self.session.recolour())
        elif key == Qt.Key.Key_Right:
            self._show(self.session.repattern())
        elif key == Qt.Key.Key_Down:
            self._show(self.session.previous())
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.apply_wallpaper()
        elif key == Qt.Key.Key_T:
            self.cycle_theme(-1 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1)
        elif key in EFFECT_KEYS:
            self._toggle(EFFECT_KEYS[key])
        elif key in (Qt.Key.Key_Escape, Qt.Key.Key_Q):
            self.close()
        else:
            super().keyPressEvent(event)


def QSystemTrayAvailable() -> bool:  # noqa: N802 (matches the Qt spelling it wraps)
    from PySide6.QtWidgets import QSystemTrayIcon

    return QSystemTrayIcon.isSystemTrayAvailable()
