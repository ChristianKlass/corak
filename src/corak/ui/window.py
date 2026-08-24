"""Main window.

The wallpaper is the point of the application, so it takes the whole upper
surface and the chrome sits under it as a single quiet bar. Two things that
were invisible are now stated: which key does what, and what the design's
identity is.
"""

from __future__ import annotations

import time
from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication, QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import effects as fx
from ..config import Settings, save
from ..design import Design
from ..frame import NOMINAL_PX_PER_MM
from ..rotation import describe, rotate
from ..screens import detect, primary_size
from ..session import Session
from ..store import Store
from ..themes import all_themes
from ..wallpaper import WallpaperError
from .preview import PreviewWidget
from .settings import SettingsDialog
from .style import scheme, stylesheet
from .widgets import Field, KeyCap, Row, Separator

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

# Left is back. It breaks the symmetry of one axis per horizontal key, but
# back-is-left is a far stronger habit than any symmetry an interface can
# invent, and reaching for it and getting new colours is a worse surprise.
#
# Ordered so the pair that mirror each other sit together and the odd one out
# is last. The verbs are dim and the nouns are not: what changes between the
# two rows is the only thing worth reading twice.
ARROWS = (
    ("↓", (("keep", False), ("pattern", True), ("·", False),
           ("reroll", False), ("colours", True))),
    ("→", (("keep", False), ("colours", True), ("·", False),
           ("reroll", False), ("pattern", True))),
    ("↑", (("reroll", False), ("both", True))),
    ("←", (("undo — previous design", False),)),
)


def _primary_density() -> float:
    """Pixel density of the screen the preview stands in for."""
    try:
        screens = detect()
    except RuntimeError:
        return NOMINAL_PX_PER_MM
    for screen in screens:
        if screen.primary:
            return screen.px_per_mm
    return screens[0].px_per_mm if screens else NOMINAL_PX_PER_MM


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
        self.density = _primary_density()
        self.effects = dict(settings.active_theme().effects)
        self.scheme = scheme()
        self.setStyleSheet(stylesheet(self.scheme))

        self.setWindowTitle("corak")
        self.preview = PreviewWidget(self)
        self.preview.set_ground(self.scheme.sunken)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.preview, 1)
        layout.addWidget(self._build_bar())

        central = QWidget(self)
        central.setLayout(layout)
        self.setCentralWidget(central)
        # Its own minimum, not a number picked in advance: opening narrower than
        # the bar needs clips the hints rather than shrinking anything.
        self.resize(max(1180, self.minimumSizeHint().width()), 700)

        self._show(session.current)

    # -- chrome ------------------------------------------------------------

    def _build_bar(self) -> QWidget:
        bar = QFrame(self)
        bar.setObjectName("bar")

        grid = QGridLayout(bar)
        grid.setContentsMargins(18, 12, 18, 12)
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(0, 1)

        grid.addWidget(self._build_identity(), 0, 0)
        grid.addWidget(self._build_meta(), 1, 0)
        grid.addWidget(self._build_arrows(), 0, 1, 2, 1)
        grid.addWidget(self._build_actions(), 0, 2, 2, 1)
        return bar

    def _build_identity(self) -> QWidget:
        row = Row(10, self)
        self.field_theme = row.add(Field("theme"))
        row.add(Separator())
        self.field_pattern = row.add(Field("pattern"))
        row.add(Separator())
        self.field_pattern_seed = row.add(Field("shape seed"))
        row.add(Separator())
        self.field_palette_seed = row.add(Field("colour seed"))

        self.copy_button = QPushButton("Copy", self)
        self.copy_button.setObjectName("quiet")
        self.copy_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.copy_button.setToolTip("Copy the design id, for corak --design")
        self.copy_button.clicked.connect(self._copy_identity)
        row.layout_.addSpacing(6)
        row.add(self.copy_button)
        row.add_stretch()
        return row

    def _build_meta(self) -> QWidget:
        row = Row(6, self)
        self.meta = QLabel("", self)
        self.meta.setObjectName("meta")
        row.add(self.meta)
        row.layout_.addSpacing(10)
        self.chips = Row(6, self)
        row.add(self.chips)
        row.add_stretch()
        self.warning = QLabel("", self)
        self.warning.setObjectName("warning")
        row.add(self.warning)
        return row

    def _build_arrows(self) -> QWidget:
        """The arrow keys, one per line."""
        holder = QWidget(self)
        holder.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        column = QVBoxLayout(holder)
        # Room on the right: the longest line otherwise runs to the edge of the
        # block and sits against the next column with nothing between them.
        column.setContentsMargins(0, 0, 24, 0)
        column.setSpacing(5)

        heading = QLabel("arrow keys", self)
        heading.setObjectName("section")
        column.addWidget(heading)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(9)
        grid.setVerticalSpacing(4)
        for row, (glyph, parts) in enumerate(ARROWS):
            key = KeyCap(glyph, parent=self)
            key.setFixedWidth(26)
            grid.addWidget(key, row, 0)

            label = QLabel(self._phrase(parts), self)
            label.setObjectName("hint")
            label.setTextFormat(Qt.TextFormat.RichText)
            grid.addWidget(label, row, 1, Qt.AlignmentFlag.AlignVCenter)
        column.addLayout(grid)
        return holder

    def _phrase(self, parts: tuple[tuple[str, bool], ...]) -> str:
        """Dim the verbs, leave the nouns alone."""
        pieces = []
        for text, emphasised in parts:
            colour = self.scheme.text if emphasised else self.scheme.faint
            pieces.append(f'<span style="color:{colour}">{text}</span>')
        return " ".join(pieces)

    def _build_actions(self) -> QWidget:
        holder = QWidget(self)
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(9)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.settings_button = QPushButton("Settings…", self)
        self.settings_button.clicked.connect(self.open_settings)
        self.apply_button = QPushButton("Set as wallpaper", self)
        self.apply_button.setObjectName("primary")
        self.apply_button.clicked.connect(self.apply_wallpaper)
        for button in (self.settings_button, self.apply_button):
            # Focus stays on the window so the arrow keys keep working after a
            # button has been clicked.
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            buttons.addWidget(button)
        column.addLayout(buttons)

        # Enter is not listed: the primary button directly above says what it
        # does, and repeating it cost the width that clipped the row below.
        for keys, caption in (
            (("T", "⇧T"), "next / previous theme"),
            (("C", "D", "V", "G"), "calm · darken · vignette · grain"),
        ):
            line = Row(5, self)
            for key in keys:
                line.add(KeyCap(key, wide=len(key) > 1, parent=self))
            label = QLabel(caption, self)
            label.setObjectName("hint")
            line.add(label)
            line.add_stretch()
            column.addWidget(line)
        return holder

    # -- rendering ---------------------------------------------------------

    def _preview_size(self) -> tuple[int, int]:
        w, h = self.target
        scale = min(1.0, PREVIEW_LONG_EDGE / max(w, h))
        return max(1, round(w * scale)), max(1, round(h * scale))

    def _preview_density(self, width: int) -> float:
        """Pixel density for the preview, matched to the target screen.

        Features are sized in millimetres, so a smaller image is a physically
        smaller screen and shows fewer, larger shapes. Previewing at the
        target's own density showed something the wallpaper would never be.
        """
        return self.density * width / max(1, self.target[0])

    def _show(self, design: Design | None) -> None:
        if design is None:
            self.meta.setText("nothing further back in history")
            return
        w, h = self._preview_size()
        started = time.perf_counter()
        image = self.session.engine.render(design, w, h, self.effects, self._preview_density(w))
        elapsed = (time.perf_counter() - started) * 1000.0
        self.preview.set_image(image)

        theme = self.settings.active_theme()
        self.setWindowTitle(f"corak — {theme.name}")
        self.field_theme.set_value(design.theme or "—")
        self.field_pattern.set_value(design.pattern)
        self.field_pattern_seed.set_value(f"{design.pattern_seed:06x}")
        self.field_palette_seed.set_value(f"{design.palette_seed:06x}")
        self.meta.setText(
            f"target {self.target[0]}×{self.target[1]}   "
            f"preview {w}×{h}   drawn in {elapsed:.0f} ms"
        )
        self._show_effects()
        self.design_changed.emit(design)

    def _show_effects(self) -> None:
        while self.chips.layout_.count():
            item = self.chips.layout_.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for name in fx.ORDER:
            strength = self.effects.get(name)
            if not strength:
                continue
            chip = QLabel(f"{name} {strength:.2f}", self)
            chip.setObjectName("chip")
            self.chips.add(chip)
        off = [n for n in fx.ORDER if not self.effects.get(n)]
        if off:
            label = QLabel(", ".join(off) + " off", self)
            label.setObjectName("chipOff")
            self.chips.add(label)
        self.warning.setText(
            "; ".join(filter(None, (fx.warning(n) for n in self.effects)))
        )

    # -- actions -----------------------------------------------------------

    def _copy_identity(self) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self.session.current.slug())
            self.copy_button.setText("Copied")

    def apply_wallpaper(self) -> None:
        design = self.session.current
        self.apply_button.setText("Setting…")
        self.apply_button.setEnabled(False)
        QGuiApplication.processEvents()
        try:
            _, targets = rotate(
                self.settings, self.session.engine, self.store, design=design,
                effects=self.effects,
            )
        except WallpaperError as exc:
            self.meta.setText(f"could not set wallpaper: {exc}")
        else:
            self.meta.setText(describe(design, targets))
        finally:
            self.apply_button.setText("Set as wallpaper")
            self.apply_button.setEnabled(True)

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        dialog.settings_changed.connect(self._settings_changed)
        dialog.exec()

    def _settings_changed(self, settings: Settings) -> None:
        """Applied as they are edited: a preview redraw costs under 30 ms."""
        theme_changed = settings.theme != self.settings.theme
        # Only the rotation settings reach systemctl. Everything here runs on
        # every slider tick, and shelling out on each one would make dragging
        # one unusable.
        schedule_changed = (
            settings.rotate != self.settings.rotate
            or settings.interval_minutes != self.settings.interval_minutes
        )
        self.settings = settings
        save(settings)
        theme = settings.active_theme()
        self.session.engine.enabled = list(settings.patterns)
        self.session.engine.themes = tuple(settings.themes())
        self.effects = dict(theme.effects)
        if schedule_changed:
            self._apply_schedule()
        if theme_changed:
            self._show(self.session.set_theme(theme))
        else:
            self.session.theme = theme
            self._show(self.session.current)

    def cycle_theme(self, step: int = 1) -> None:
        themes = all_themes(self.settings.themes())
        current = self.settings.active_theme()
        index = next((i for i, t in enumerate(themes) if t.id == current.id), 0)
        theme = themes[(index + step) % len(themes)]
        self.settings = replace(self.settings, theme=theme.id)
        self.effects = dict(theme.effects)
        self._show(self.session.set_theme(theme))

    def _apply_schedule(self) -> None:
        from .. import scheduler

        try:
            if self.settings.rotate:
                scheduler.enable(self.settings.interval_minutes)
            else:
                scheduler.disable()
        except scheduler.SchedulerError as exc:
            self.meta.setText(f"could not change the schedule: {exc}")

    def _toggle(self, name: str) -> None:
        if name in self.effects:
            del self.effects[name]
        else:
            self.effects[name] = 0.7 if name == "calm" else 0.6
        self._show(self.session.current)

    def closeEvent(self, event) -> None:
        # Hiding rather than quitting keeps the tray icon usable; the tray's
        # Quit action is what ends the process.
        from PySide6.QtWidgets import QSystemTrayIcon

        if self.isVisible() and QSystemTrayIcon.isSystemTrayAvailable():
            event.ignore()
            self.hide()
            return
        super().closeEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key != Qt.Key.Key_C:
            self.copy_button.setText("Copy")
        if key == Qt.Key.Key_Up:
            self._show(self.session.regenerate())
        elif key == Qt.Key.Key_Left:
            self._show(self.session.previous())
        elif key == Qt.Key.Key_Right:
            self._show(self.session.repattern())
        elif key == Qt.Key.Key_Down:
            self._show(self.session.recolour())
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
