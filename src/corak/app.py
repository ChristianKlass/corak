"""Entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .engine import Engine
from .screens import configure_scaling, primary_size
from .session import Session
from .ui.window import MainWindow


def main(argv: list[str] | None = None) -> int:
    configure_scaling()
    app = QApplication(argv if argv is not None else sys.argv)
    window = MainWindow(Session(Engine()), primary_size())
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
