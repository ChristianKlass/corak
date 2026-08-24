"""Colours and the stylesheet.

Qt styles with QSS, a subset of CSS: fills, borders, radii, padding, fonts and
widget gradients, and nothing else. No shadows, transforms or animation. Every
colour lives here so the two schemes stay in step.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QGuiApplication, QPalette

SANS = "'Noto Sans', 'DejaVu Sans', sans-serif"
MONO = "'Noto Sans Mono', 'DejaVu Sans Mono', monospace"


@dataclass(frozen=True)
class Scheme:
    window: str
    bar: str
    sunken: str
    line: str
    line_strong: str
    text: str
    muted: str
    faint: str
    accent: str
    accent_deep: str
    accent_text: str
    key_face: str


DARK = Scheme(
    window="#1b1e21",
    bar="#1f2226",
    sunken="#16181a",
    line="#33383d",
    line_strong="#4d545b",
    text="#e8eaec",
    muted="#8b9299",
    faint="#6d757d",
    accent="#4a9edb",
    accent_deep="#2b74ad",
    accent_text="#0e1418",
    key_face="#2a2f34",
)

LIGHT = Scheme(
    window="#fbfbfc",
    bar="#eff0f1",
    sunken="#e4e5e7",
    line="#c9cccf",
    line_strong="#9098a0",
    text="#1b1e21",
    muted="#5b636b",
    faint="#767d83",
    accent="#2b74ad",
    accent_deep="#245f8d",
    accent_text="#ffffff",
    key_face="#ffffff",
)


def scheme() -> Scheme:
    """Follow the desktop rather than deciding for it."""
    app = QGuiApplication.instance()
    if not isinstance(app, QGuiApplication):
        return DARK
    ground = app.palette().color(QPalette.ColorRole.Window)
    return DARK if ground.lightness() < 128 else LIGHT


def stylesheet(s: Scheme) -> str:
    return f"""
QWidget {{
    background: {s.window};
    color: {s.text};
    font-family: {SANS};
    font-size: 12px;
}}
QMainWindow, QDialog {{ background: {s.window}; }}
/* Labels inherit the widget fill otherwise, and every caption in the bar shows
   as a box in the window's colour rather than the bar's. Anything that wants a
   fill sets one below, and an id selector outranks this. */
QLabel, QCheckBox {{ background: transparent; }}

#bar {{
    background: {s.bar};
    border-top: 1px solid {s.line};
}}

#value {{ font-family: {MONO}; font-size: 15px; color: {s.text}; }}
#valueDim {{ font-family: {MONO}; font-size: 15px; color: {s.faint}; }}
#fieldLabel {{
    font-size: 10px; color: {s.faint};
    text-transform: uppercase; letter-spacing: 1px;
}}
#meta {{ font-family: {MONO}; font-size: 11px; color: {s.muted}; }}
#metaLabel {{ font-size: 10px; color: {s.faint}; letter-spacing: 1px; }}
#hint {{ font-size: 11px; color: {s.faint}; }}
#warning {{ font-size: 11px; color: {s.accent}; }}

#chip {{
    font-family: {MONO}; font-size: 11px; color: {s.text};
    background: {s.key_face}; border: 1px solid {s.line};
    border-radius: 4px; padding: 2px 7px;
}}
#chipOff {{ font-size: 11px; color: {s.faint}; padding: 2px 0; }}

#key {{
    font-family: {MONO}; font-size: 12px; color: {s.text};
    background: {s.key_face};
    border: 1px solid {s.line_strong};
    border-radius: 4px;
    padding: 3px 0;
    min-width: 24px;
}}
#keyWide {{
    font-family: {MONO}; font-size: 11px; color: {s.text};
    background: {s.key_face};
    border: 1px solid {s.line_strong};
    border-radius: 4px;
    padding: 3px 7px;
}}

QPushButton {{
    background: {s.bar}; color: {s.text};
    border: 1px solid {s.line_strong}; border-radius: 5px;
    padding: 6px 14px;
}}
QPushButton:hover {{ border-color: {s.accent}; }}
QPushButton:disabled {{ color: {s.faint}; border-color: {s.line}; }}
QPushButton#primary {{
    background: {s.accent}; color: {s.accent_text};
    border: 1px solid {s.accent_deep}; font-weight: 600;
}}
QPushButton#primary:hover {{ background: {s.accent_deep}; color: #ffffff; }}
QPushButton#primary:disabled {{ background: {s.line}; color: {s.faint}; border-color: {s.line}; }}
QPushButton#quiet {{
    background: transparent; border: 1px solid {s.line};
    color: {s.muted}; padding: 3px 9px; font-size: 11px;
}}
QPushButton#quiet:hover {{ color: {s.text}; border-color: {s.line_strong}; }}

#section {{
    font-size: 10px; color: {s.faint};
    text-transform: uppercase; letter-spacing: 1.4px;
}}
#card {{
    background: {s.bar};
    border: 1px solid {s.line};
    border-radius: 6px;
}}
#badge {{
    font-size: 10px; color: {s.accent};
    border: 1px solid {s.accent}; border-radius: 3px; padding: 1px 5px;
}}

QListWidget {{
    background: {s.sunken};
    border: 1px solid {s.line};
    border-radius: 6px;
    outline: none;
}}
QListWidget::item {{
    border-bottom: 1px solid {s.line};
    border-left: 3px solid transparent;
}}
/* Marked with a rule and a lift rather than filled with the accent: a solid
   accent behind a row makes its description unreadable, and the description is
   how a theme is chosen. */
QListWidget::item:selected {{
    background: {s.key_face};
    border-left: 3px solid {s.accent};
}}

QSlider::groove:horizontal {{
    height: 3px; background: {s.line_strong}; border-radius: 2px;
}}
QSlider::sub-page:horizontal {{ background: {s.accent}; border-radius: 2px; }}
QSlider::sub-page:horizontal:disabled {{ background: {s.line_strong}; }}
QSlider::groove:horizontal:disabled {{ background: {s.line}; }}
QSlider::handle:horizontal {{
    background: {s.text}; border: none;
    width: 12px; height: 12px; margin: -5px 0; border-radius: 6px;
}}
QSlider::handle:horizontal:disabled {{ background: {s.line_strong}; }}

QCheckBox {{ spacing: 7px; }}
QCheckBox::indicator {{
    width: 13px; height: 13px; border-radius: 3px;
    border: 1px solid {s.line_strong}; background: {s.sunken};
}}
QCheckBox::indicator:checked {{ background: {s.accent}; border-color: {s.accent_deep}; }}
QCheckBox::indicator:disabled {{ border-color: {s.line}; }}

QSpinBox {{
    background: {s.sunken}; border: 1px solid {s.line};
    border-radius: 4px; padding: 3px 4px;
    font-family: {MONO};
    max-width: 74px;
}}
QSpinBox:focus {{ border-color: {s.accent}; }}

QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{
    background: {s.line_strong}; border-radius: 5px; min-height: 30px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QToolTip {{
    background: {s.bar}; color: {s.text};
    border: 1px solid {s.line_strong}; padding: 4px 6px;
}}
"""
