"""The settings window.

Themes are chosen, not built. Starting from nothing means answering a dozen
questions before seeing anything, so the controls here adjust a theme that
already works -- and any adjustment saves as a variant of it rather than
overwriting the original.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
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

SCALE_RANGE = (60, 200)


class EffectRow(QWidget):
    """A checkbox and a strength slider for one effect."""

    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.name = name
        self.check = QCheckBox(name, self)
        self.slider = QSlider(Qt.Orientation.Horizontal, self)
        self.slider.setRange(0, 100)
        self.value = QLabel("0.60", self)
        self.value.setMinimumWidth(38)

        self.check.toggled.connect(self.slider.setEnabled)
        self.slider.valueChanged.connect(lambda v: self.value.setText(f"{v / 100:.2f}"))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.check.setMinimumWidth(90)
        layout.addWidget(self.check)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.value)

        caveat = fx.warning(name)
        if caveat:
            self.setToolTip(caveat)
        self.set_strength(None)

    def set_strength(self, strength: float | None) -> None:
        self.check.setChecked(strength is not None)
        self.slider.setValue(round((strength if strength is not None else 0.6) * 100))
        self.slider.setEnabled(strength is not None)

    def strength(self) -> float | None:
        return self.slider.value() / 100.0 if self.check.isChecked() else None


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("corak settings")
        self.setMinimumWidth(480)
        self._settings = settings

        self.themes = all_themes(settings.themes())
        self.theme_box = QComboBox(self)
        for theme in self.themes:
            self.theme_box.addItem(theme.name, theme.id)
        self.theme_box.setCurrentIndex(
            max(0, next((i for i, t in enumerate(self.themes) if t.id == settings.theme), 0))
        )
        self.theme_box.currentIndexChanged.connect(self._load_theme)

        self.description = QLabel(self)
        self.description.setWordWrap(True)
        self.description.setEnabled(False)

        self.reset_button = QPushButton("Reset to original", self)
        self.reset_button.clicked.connect(self._reset_theme)

        self.scale = QSlider(Qt.Orientation.Horizontal, self)
        self.scale.setRange(*SCALE_RANGE)
        self.scale_value = QLabel(self)
        self.scale.valueChanged.connect(lambda v: self.scale_value.setText(f"{v / 100:.2f}x"))

        self.effects = [EffectRow(name, self) for name in fx.ORDER]

        self.interval = QSpinBox(self)
        self.interval.setRange(MIN_INTERVAL, MAX_INTERVAL)
        self.interval.setValue(settings.interval_minutes)
        self.interval.setSuffix(" min")

        self.keep = QSpinBox(self)
        self.keep.setRange(1, 500)
        self.keep.setValue(settings.keep)
        self.keep.setSuffix(" images")

        self.rotate = QCheckBox("Change the wallpaper automatically", self)
        self.rotate.setChecked(settings.rotate)
        self.schedule = QLabel(self)
        self.schedule.setWordWrap(True)
        self.schedule.setEnabled(False)

        self.patterns = {name: QCheckBox(name, self) for name in names()}
        for name, box in self.patterns.items():
            box.setChecked(name in settings.patterns)
            # Unchecking the last one would leave nothing to generate.
            box.toggled.connect(self._guard_patterns)

        self.setLayout(self._build())
        self._load_theme()
        self._refresh_schedule()
        self._guard_patterns()

    # -- layout ------------------------------------------------------------

    def _build(self) -> QVBoxLayout:
        theme_box = QGroupBox("Theme", self)
        theme_layout = QVBoxLayout(theme_box)
        picker = QHBoxLayout()
        picker.addWidget(self.theme_box, 1)
        picker.addWidget(self.reset_button)
        theme_layout.addLayout(picker)
        theme_layout.addWidget(self.description)

        size = QHBoxLayout()
        size.addWidget(QLabel("Shape size", self))
        size.addWidget(self.scale, 1)
        size.addWidget(self.scale_value)
        theme_layout.addLayout(size)

        for row in self.effects:
            theme_layout.addWidget(row)
        caveats = [f"{n}: {fx.warning(n)}" for n in fx.ORDER if fx.warning(n)]
        if caveats:
            note = QLabel("\n".join(caveats), self)
            note.setWordWrap(True)
            note.setEnabled(False)
            theme_layout.addWidget(note)

        pattern_box = QGroupBox("Patterns", self)
        pattern_layout = QVBoxLayout(pattern_box)
        for box in self.patterns.values():
            pattern_layout.addWidget(box)

        form = QFormLayout()
        form.addRow("Change every", self.interval)
        form.addRow("Keep", self.keep)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(theme_box)
        layout.addWidget(pattern_box)
        layout.addWidget(self.rotate)
        layout.addLayout(form)
        layout.addWidget(self.schedule)
        layout.addWidget(buttons)
        return layout

    # -- behaviour ---------------------------------------------------------

    def selected_theme(self) -> Theme:
        return self.themes[max(0, self.theme_box.currentIndex())]

    def _base_theme(self) -> Theme:
        """The built-in a selection came from, or the selection itself."""
        chosen = self.selected_theme()
        if not chosen.derived_from:
            return chosen
        return next((t for t in self.themes if t.id == chosen.derived_from), chosen)

    def _load_theme(self) -> None:
        theme = self.selected_theme()
        self.description.setText(theme.description)
        self.scale.setValue(round(theme.scale * 100))
        for row in self.effects:
            row.set_strength(theme.effects.get(row.name))
        self.reset_button.setEnabled(bool(theme.derived_from))

    def _reset_theme(self) -> None:
        base = self._base_theme()
        self.scale.setValue(round(base.scale * 100))
        for row in self.effects:
            row.set_strength(base.effects.get(row.name))

    def _guard_patterns(self) -> None:
        checked = [box for box in self.patterns.values() if box.isChecked()]
        for box in self.patterns.values():
            box.setEnabled(not (len(checked) == 1 and box.isChecked()))

    def _refresh_schedule(self) -> None:
        line = scheduler.next_run()
        self.schedule.setText(f"Next: {line}" if line else "Not currently scheduled.")

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

        # Matching the original exactly means the user has reset it, so the
        # variant is dropped rather than saved as an identical copy.
        if effects == base.effects and abs(scale - base.scale) < 1e-6:
            return settings.with_theme(base).normalised()
        return settings.with_theme(base.derive(effects=effects, scale=scale)).normalised()
