"""The settings window."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .. import effects as fx
from .. import scheduler
from ..config import MAX_INTERVAL, MIN_INTERVAL, Settings
from ..patterns import names


class EffectRow(QWidget):
    """A checkbox and a strength slider for one effect."""

    def __init__(self, name: str, strength: float | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.name = name
        self.check = QCheckBox(name, self)
        self.check.setChecked(strength is not None)
        self.slider = QSlider(Qt.Orientation.Horizontal, self)
        self.slider.setRange(0, 100)
        self.slider.setValue(round((strength if strength is not None else 0.6) * 100))
        self.slider.setEnabled(strength is not None)
        self.value = QLabel(f"{self.slider.value() / 100:.2f}", self)
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

    def enabled(self) -> bool:
        return self.check.isChecked()

    def strength(self) -> float:
        return self.slider.value() / 100.0


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("corak settings")
        self.setMinimumWidth(460)

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

        self.effects = [EffectRow(name, settings.effects.get(name), self) for name in fx.ORDER]

        pattern_box = QGroupBox("Patterns", self)
        pattern_layout = QVBoxLayout(pattern_box)
        for box in self.patterns.values():
            pattern_layout.addWidget(box)

        effect_box = QGroupBox("Effects", self)
        effect_layout = QVBoxLayout(effect_box)
        for row in self.effects:
            effect_layout.addWidget(row)
        caveats = [f"{n}: {fx.warning(n)}" for n in fx.ORDER if fx.warning(n)]
        if caveats:
            note = QLabel("\n".join(caveats), self)
            note.setWordWrap(True)
            note.setEnabled(False)
            effect_layout.addWidget(note)

        form = QFormLayout()
        form.addRow("Change every", self.interval)
        form.addRow("Keep", self.keep)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.rotate)
        layout.addLayout(form)
        layout.addWidget(self.schedule)
        layout.addWidget(pattern_box)
        layout.addWidget(effect_box)
        layout.addWidget(buttons)

        self._refresh_schedule()

    def _guard_patterns(self) -> None:
        checked = [box for box in self.patterns.values() if box.isChecked()]
        for box in self.patterns.values():
            box.setEnabled(not (len(checked) == 1 and box.isChecked()))

    def _refresh_schedule(self) -> None:
        line = scheduler.next_run()
        self.schedule.setText(f"Next: {line}" if line else "Not currently scheduled.")

    def result_settings(self) -> Settings:
        return Settings(
            interval_minutes=self.interval.value(),
            patterns=[name for name, box in self.patterns.items() if box.isChecked()],
            effects={row.name: row.strength() for row in self.effects if row.enabled()},
            keep=self.keep.value(),
            rotate=self.rotate.isChecked(),
        ).normalised()
