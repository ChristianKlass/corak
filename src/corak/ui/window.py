"""Main window: shows the current design and owns the key bindings."""

from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from .. import effects as fx
from ..design import Design
from ..session import Session
from ..wallpaper import WallpaperError, render_and_apply
from .preview import PreviewWidget

# Rendering the full panel resolution on every keypress would stall the window
# for a noticeable beat; the preview keeps the target aspect and only the pixel
# count comes down.  Full resolution is produced when the wallpaper is applied.
PREVIEW_LONG_EDGE = 1600


EFFECT_KEYS = {
    Qt.Key.Key_C: "calm",
    Qt.Key.Key_D: "darken",
    Qt.Key.Key_V: "vignette",
    Qt.Key.Key_G: "grain",
}


class MainWindow(QMainWindow):
    def __init__(self, session: Session, target: tuple[int, int]) -> None:
        super().__init__()
        self.session = session
        self.target = target
        self.setWindowTitle("corak")

        # Toggled from the keyboard so the effects can be judged against the
        # same design; step 4 moves these into saved settings.
        self.effects: dict[str, float] = {}
        self._warning = ""

        self.preview = PreviewWidget(self)
        self.apply_button = QPushButton("Set as wallpaper", self)
        self.apply_button.setDefault(True)
        self.apply_button.clicked.connect(self.apply_wallpaper)
        # Focus stays on the window so the arrow keys keep working after the
        # button has been clicked.
        self.apply_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        buttons = QHBoxLayout()
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

    def _toggle(self, name: str) -> None:
        if name in self.effects:
            del self.effects[name]
            self._warning = ""
        else:
            self.effects[name] = 0.7 if name == "calm" else 0.6
            self._warning = fx.warning(name) or ""
        self._show(self.session.current)

    def apply_wallpaper(self) -> None:
        design = self.session.current
        self.statusBar().showMessage(f"rendering {design} at native size...")
        self.apply_button.setEnabled(False)
        try:
            targets = render_and_apply(self.session.engine, design, self.effects)
        except WallpaperError as exc:
            self.statusBar().showMessage(f"could not set wallpaper: {exc}", 8000)
        else:
            where = ", ".join(f"{t.screen.name} {t.screen.width}x{t.screen.height}" for t in targets)
            self.statusBar().showMessage(f"set on {where}", 6000)
        finally:
            self.apply_button.setEnabled(True)

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
        elif key in EFFECT_KEYS:
            self._toggle(EFFECT_KEYS[key])
        elif key in (Qt.Key.Key_Escape, Qt.Key.Key_Q):
            self.close()
        else:
            super().keyPressEvent(event)
