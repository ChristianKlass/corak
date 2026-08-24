"""Settings.

Changes apply as they are made -- a preview redraw costs under thirty
milliseconds, so there is nothing to wait for and no reason to make someone
confirm. There is one button, and it closes the window.

Themes are chosen, not built. Starting from nothing means answering a dozen
questions before seeing anything, so the controls adjust a theme that already
works and any adjustment saves as a variant, leaving the original alone.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .. import effects as fx
from .. import scheduler
from ..config import MAX_INTERVAL, MIN_INTERVAL, Settings
from ..patterns import names
from ..themes import Theme, all_themes
from .style import scheme, stylesheet
from .widgets import Swatches

SCALE_RANGE = (60, 200)


class ThemeRow(QWidget):
    """A theme's name, what it looks like, and what it is called."""

    def __init__(self, theme: Theme, colours: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)

        head = QHBoxLayout()
        head.setSpacing(7)
        name = QLabel(theme.name, self)
        name.setStyleSheet("font-weight: 600;")
        head.addWidget(name)
        if theme.derived_from:
            badge = QLabel("modified", self)
            badge.setObjectName("badge")
            head.addWidget(badge)
        head.addStretch(1)
        layout.addLayout(head)

        if theme.description:
            description = QLabel(theme.description, self)
            description.setObjectName("hint")
            description.setWordWrap(True)
            layout.addWidget(description)

        layout.addWidget(Swatches(colours, scheme(), self))


class EffectRow(QWidget):
    """A checkbox and a strength slider for one effect."""

    changed = Signal()

    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.name = name
        self.check = QCheckBox(name, self)
        self.slider = QSlider(Qt.Orientation.Horizontal, self)
        self.slider.setRange(0, 100)
        self.value = QLabel("0.00", self)
        self.value.setObjectName("meta")
        self.value.setMinimumWidth(34)

        self.check.toggled.connect(self.slider.setEnabled)
        self.check.toggled.connect(self.changed)
        self.slider.valueChanged.connect(lambda v: self.value.setText(f"{v / 100:.2f}"))
        self.slider.valueChanged.connect(self._slid)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.check.setMinimumWidth(78)
        layout.addWidget(self.check)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.value)

        caveat = fx.warning(name)
        if caveat:
            self.setToolTip(caveat)
        self.set_strength(None)

    def _slid(self) -> None:
        if self.check.isChecked():
            self.changed.emit()

    def set_strength(self, strength: float | None) -> None:
        for widget in (self.check, self.slider):
            widget.blockSignals(True)
        self.check.setChecked(strength is not None)
        self.slider.setValue(round((strength if strength is not None else 0.6) * 100))
        self.slider.setEnabled(strength is not None)
        self.value.setText(f"{self.slider.value() / 100:.2f}")
        for widget in (self.check, self.slider):
            widget.blockSignals(False)

    def strength(self) -> float | None:
        return self.slider.value() / 100.0 if self.check.isChecked() else None


class SettingsDialog(QDialog):
    settings_changed = Signal(Settings)

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("corak — Settings")
        self.setMinimumWidth(520)
        self.resize(520, 780)
        self.setStyleSheet(stylesheet(scheme()))
        self._settings = settings
        self._loading = False

        self.themes = all_themes(settings.themes())
        self._build()
        self._load_theme()
        self._refresh_schedule()
        self._guard_patterns()

    # -- construction ------------------------------------------------------

    def _section(self, title: str) -> QLabel:
        label = QLabel(title, self)
        label.setObjectName("section")
        return label

    def _card(self) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame(self)
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        return card, layout

    def _build(self) -> None:
        page = QWidget(self)
        column = QVBoxLayout(page)
        column.setContentsMargins(18, 18, 18, 6)
        column.setSpacing(9)

        # theme -----------------------------------------------------------
        column.addWidget(self._section("theme"))
        card, inner = self._card()

        head = QHBoxLayout()
        self.theme_name = QLabel("", self)
        self.theme_name.setStyleSheet("font-weight: 600; font-size: 13px;")
        head.addWidget(self.theme_name)
        head.addStretch(1)
        self.reset_button = QPushButton("Reset to original", self)
        self.reset_button.setObjectName("quiet")
        self.reset_button.clicked.connect(self._reset_theme)
        head.addWidget(self.reset_button)
        inner.addLayout(head)

        self.theme_list = QListWidget(self)
        self.theme_list.setSpacing(0)
        for theme in self.themes:
            item = QListWidgetItem(self.theme_list)
            row = ThemeRow(theme, list(theme.colors), self)
            item.setSizeHint(QSize(0, row.sizeHint().height()))
            self.theme_list.addItem(item)
            self.theme_list.setItemWidget(item, row)
        self.theme_list.setCurrentRow(
            max(0, next((i for i, t in enumerate(self.themes) if t.id == self._settings.theme), 0))
        )
        self.theme_list.setMinimumHeight(210)
        self.theme_list.currentRowChanged.connect(self._theme_picked)
        inner.addWidget(self.theme_list)
        column.addWidget(card)

        # shape -------------------------------------------------------------
        column.addWidget(self._section("shape"))
        card, inner = self._card()
        size_row = QHBoxLayout()
        size_row.setSpacing(10)
        size_row.addWidget(QLabel("Shape size", self))
        self.scale = QSlider(Qt.Orientation.Horizontal, self)
        self.scale.setRange(*SCALE_RANGE)
        self.scale.valueChanged.connect(self._emit)
        size_row.addWidget(self.scale, 1)
        self.scale_value = QLabel("", self)
        self.scale_value.setObjectName("meta")
        self.scale_value.setMinimumWidth(38)
        self.scale.valueChanged.connect(lambda v: self.scale_value.setText(f"{v / 100:.2f}×"))
        size_row.addWidget(self.scale_value)
        inner.addLayout(size_row)
        bounds = QHBoxLayout()
        for text, align in (("0.6×", Qt.AlignmentFlag.AlignLeft), ("2.0×", Qt.AlignmentFlag.AlignRight)):
            label = QLabel(text, self)
            label.setObjectName("hint")
            bounds.addWidget(label, 1, align)
        inner.addLayout(bounds)
        column.addWidget(card)

        # effects -----------------------------------------------------------
        column.addWidget(self._section("effects"))
        card, inner = self._card()
        self.effects = []
        for name in fx.ORDER:
            row = EffectRow(name, self)
            row.changed.connect(self._emit)
            self.effects.append(row)
            inner.addWidget(row)
        caveats = [fx.warning(n) for n in fx.ORDER if fx.warning(n)]
        if caveats:
            note = QLabel(" ".join(caveats), self)
            note.setObjectName("hint")
            note.setWordWrap(True)
            inner.addWidget(note)
        column.addWidget(card)

        # patterns ----------------------------------------------------------
        column.addWidget(self._section("patterns"))
        card, inner = self._card()
        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(6)
        self.patterns = {}
        for i, name in enumerate(names()):
            box = QCheckBox(name, self)
            box.setChecked(name in self._settings.patterns)
            box.toggled.connect(self._guard_patterns)
            box.toggled.connect(self._emit)
            self.patterns[name] = box
            grid.addWidget(box, i // 2, i % 2)
        inner.addLayout(grid)
        note = QLabel("At least one pattern stays enabled.", self)
        note.setObjectName("hint")
        inner.addWidget(note)
        column.addWidget(card)

        # rotation ----------------------------------------------------------
        column.addWidget(self._section("rotation"))
        card, inner = self._card()
        self.rotate = QCheckBox("Rotate automatically", self)
        self.rotate.setChecked(self._settings.rotate)
        self.rotate.toggled.connect(self._emit)
        inner.addWidget(self.rotate)

        every = QHBoxLayout()
        every.setSpacing(8)
        every.addWidget(QLabel("Every", self))
        self.interval = QSpinBox(self)
        self.interval.setRange(MIN_INTERVAL, MAX_INTERVAL)
        self.interval.setValue(self._settings.interval_minutes)
        self.interval.valueChanged.connect(self._emit)
        every.addWidget(self.interval)
        every.addWidget(QLabel("minutes", self))
        every.addStretch(1)
        inner.addLayout(every)

        keep = QHBoxLayout()
        keep.setSpacing(8)
        keep.addWidget(QLabel("Keep", self))
        self.keep = QSpinBox(self)
        self.keep.setRange(1, 500)
        self.keep.setValue(self._settings.keep)
        self.keep.valueChanged.connect(self._emit)
        keep.addWidget(self.keep)
        keep.addWidget(QLabel("generated images on disk", self))
        keep.addStretch(1)
        inner.addLayout(keep)

        self.schedule = QLabel("", self)
        self.schedule.setObjectName("hint")
        self.schedule.setWordWrap(True)
        inner.addWidget(self.schedule)
        column.addWidget(card)
        column.addStretch(1)

        scroller = QScrollArea(self)
        scroller.setWidgetResizable(True)
        scroller.setWidget(page)

        close = QPushButton("Close", self)
        close.setObjectName("primary")
        close.clicked.connect(self.accept)
        footer = QHBoxLayout()
        footer.setContentsMargins(18, 8, 18, 14)
        footer.addStretch(1)
        footer.addWidget(close)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(scroller, 1)
        outer.addLayout(footer)

    # -- behaviour ---------------------------------------------------------

    def selected_theme(self) -> Theme:
        return self.themes[max(0, self.theme_list.currentRow())]

    def _base_theme(self) -> Theme:
        """The original a selection came from, or the selection itself."""
        chosen = self.selected_theme()
        if not chosen.derived_from:
            return chosen
        return next((t for t in self.themes if t.id == chosen.derived_from), chosen)

    def _load_theme(self) -> None:
        theme = self.selected_theme()
        self._loading = True
        self.theme_name.setText(theme.name)
        self.scale.setValue(round(theme.scale * 100))
        for row in self.effects:
            row.set_strength(theme.effects.get(row.name))
        self.reset_button.setEnabled(bool(theme.derived_from))
        self._loading = False

    def _theme_picked(self) -> None:
        self._load_theme()
        self._emit()

    def _reset_theme(self) -> None:
        base = self._base_theme()
        self._loading = True
        self.scale.setValue(round(base.scale * 100))
        for row in self.effects:
            row.set_strength(base.effects.get(row.name))
        self._loading = False
        self._emit()

    def _guard_patterns(self) -> None:
        checked = [box for box in self.patterns.values() if box.isChecked()]
        for box in self.patterns.values():
            box.setEnabled(not (len(checked) == 1 and box.isChecked()))

    def _refresh_schedule(self) -> None:
        line = scheduler.next_run()
        self.schedule.setText(f"Next rotation: {line}" if line else "Not currently scheduled.")

    def _emit(self) -> None:
        if self._loading:
            return
        self._settings = self.result_settings()
        self.theme_name.setText(self._settings.active_theme().name)
        self.reset_button.setEnabled(bool(self._settings.active_theme().derived_from))
        self.settings_changed.emit(self._settings)
        self._refresh_schedule()

    def result_settings(self) -> Settings:
        chosen = self.selected_theme()
        base = self._base_theme()
        effects = {row.name: s for row in self.effects if (s := row.strength()) is not None}
        scale = self.scale.value() / 100.0

        settings = Settings(
            interval_minutes=self.interval.value(),
            patterns=[name for name, box in self.patterns.items() if box.isChecked()],
            theme=chosen.id,
            custom_themes=list(self._settings.custom_themes),
            keep=self.keep.value(),
            rotate=self.rotate.isChecked(),
        )

        # Matching the original exactly means it has been reset, so the variant
        # is dropped rather than saved as an identical copy.
        if effects == base.effects and abs(scale - base.scale) < 1e-6:
            return settings.with_theme(base).normalised()
        return settings.with_theme(base.derive(effects=effects, scale=scale)).normalised()
