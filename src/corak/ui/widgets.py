"""Small pieces shared by the window and the dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .style import Scheme


class Field(QWidget):
    """A monospace value with a small caption under it.

    The design identity is worth reading as fields rather than as one run of
    text -- it names the theme, the pattern and the two seeds, and any of them
    can be typed back into the command line.
    """

    def __init__(self, label: str, value: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.value = QLabel(value, self)
        self.value.setObjectName("value")
        self.caption = QLabel(label, self)
        self.caption.setObjectName("fieldLabel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self.value)
        layout.addWidget(self.caption)

    def set_value(self, value: str) -> None:
        self.value.setText(value)


class Separator(QLabel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("·", parent)
        self.setObjectName("valueDim")
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.setContentsMargins(0, 0, 0, 0)


class KeyCap(QLabel):
    def __init__(self, text: str, wide: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("keyWide" if wide else "key")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class Swatches(QFrame):
    """A palette shown as a strip, so a theme can be judged before choosing it."""

    def __init__(self, colors: list[str], scheme: Scheme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._colors = [QColor(c) for c in colors]
        self._line = QColor(scheme.line)
        self.setFixedHeight(14)
        self.setMinimumWidth(90)

    def set_colors(self, colors: list[str]) -> None:
        self._colors = [QColor(c) for c in colors]
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        if not self._colors:
            painter.fillRect(self.rect(), self._line)
            return
        width = self.width() / len(self._colors)
        for i, colour in enumerate(self._colors):
            painter.fillRect(
                round(i * width), 0, round(width) + 1, self.height(), colour
            )


class Row(QWidget):
    """A horizontal strip with no margins, for composing bars."""

    def __init__(self, spacing: int = 8, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.layout_ = QHBoxLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.layout_.setSpacing(spacing)

    def add(self, widget: QWidget, stretch: int = 0) -> QWidget:
        self.layout_.addWidget(widget, stretch)
        return widget

    def add_stretch(self, stretch: int = 1) -> None:
        self.layout_.addStretch(stretch)
