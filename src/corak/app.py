"""Application wiring: window, tray icon, settings and history."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from .config import load
from .engine import Engine
from .rotation import describe, rotate
from .screens import configure_scaling, primary_size
from .session import Session
from .store import Store
from .ui.tray import Tray
from .ui.window import MainWindow
from .wallpaper import WallpaperError


def run(argv: list[str] | None = None) -> int:
    configure_scaling()
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("corak")
    app.setApplicationDisplayName("corak")

    settings = load()
    store = Store()
    engine = Engine(settings.patterns)
    window = MainWindow(Session(engine), settings, store, primary_size())

    tray = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        # Closing the window leaves the tray icon behind, so the process has to
        # outlive its last window.
        app.setQuitOnLastWindowClosed(False)
        tray = Tray(engine, window)
        tray.action_next.triggered.connect(lambda: _rotate_now(window, tray))
        tray.action_show.triggered.connect(window.showNormal)
        tray.action_settings.triggered.connect(window.open_settings)
        tray.action_quit.triggered.connect(app.quit)
        tray.activated.connect(
            lambda reason: window.setVisible(not window.isVisible())
            if reason == QSystemTrayIcon.ActivationReason.Trigger
            else None
        )
        window.design_changed.connect(tray.show_design)
        tray.show()

    window.show()
    try:
        return app.exec()
    finally:
        store.close()


def _rotate_now(window: MainWindow, tray: Tray | None) -> None:
    """Generate and set a fresh wallpaper without touching the window's design."""
    try:
        design, targets = rotate(window.settings, window.session.engine, window.store)
    except WallpaperError as exc:
        if tray is not None:
            tray.showMessage("corak", str(exc), QSystemTrayIcon.MessageIcon.Warning)
        return
    if tray is not None:
        tray.show_design(design)
        tray.showMessage("corak", describe(design, targets))


def main(argv: list[str] | None = None) -> int:
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
