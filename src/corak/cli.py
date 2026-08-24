"""Command line entry point.

`--next` is the headless path the systemd timer runs; with no arguments the
window opens.
"""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="corak", description="Procedural geometric wallpapers.")
    parser.add_argument(
        "--next",
        action="store_true",
        help="generate and set the next wallpaper without opening a window",
    )
    parser.add_argument("--list-patterns", action="store_true", help="list pattern names and exit")
    parser.add_argument("--history", type=int, metavar="N", help="show the last N designs and exit")
    parser.add_argument("--version", action="version", version=f"corak {__version__}")
    return parser


def _rotate_headless() -> int:
    # No window is wanted, but QImage still needs a QGuiApplication, and the
    # offscreen plugin provides one without a display.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication

    QGuiApplication.instance() or QGuiApplication([])

    from .config import load
    from .rotation import describe, rotate
    from .store import Store
    from .wallpaper import WallpaperError

    try:
        with Store() as store:
            design, targets = rotate(load(), store=store)
    except WallpaperError as exc:
        print(f"corak: {exc}", file=sys.stderr)
        return 1
    print(describe(design, targets))
    return 0


def _show_history(limit: int) -> int:
    from .store import Store

    with Store() as store:
        for entry in store.recent(limit):
            effects = ",".join(f"{k}={v:g}" for k, v in sorted(entry.effects.items())) or "-"
            print(
                f"{entry.created_at}  {entry.design}  {entry.scheme:<10} {effects:<20} "
                f"{entry.screen} {entry.width}x{entry.height}"
            )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.list_patterns:
        from .patterns import names

        print("\n".join(names()))
        return 0
    if args.history is not None:
        return _show_history(args.history)
    if args.next:
        return _rotate_headless()

    from .app import run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
