"""Main window: shows the current design and owns the key bindings."""

from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QMainWindow, QStatusBar

from ..design import Design
from ..session import Session
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

        self.preview = PreviewWidget(self)
        self.setCentralWidget(self.preview)
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
        )

    def _toggle(self, name: str) -> None:
        if name in self.effects:
            del self.effects[name]
        else:
            self.effects[name] = 0.7 if name == "calm" else 0.6
        self._show(self.session.current)

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
        elif key in EFFECT_KEYS:
            self._toggle(EFFECT_KEYS[key])
        elif key in (Qt.Key.Key_Escape, Qt.Key.Key_Q):
            self.close()
        else:
            super().keyPressEvent(event)
