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
    parser.add_argument("--list-themes", action="store_true", help="list theme names and exit")
    parser.add_argument(
        "--add-theme",
        metavar="FILE",
        help="check a theme document and install it, or '-' to read one from stdin",
    )
    parser.add_argument("--history", type=int, metavar="N", help="show the last N designs and exit")
    parser.add_argument(
        "--design",
        metavar="SLUG",
        help="set one exact design, named the way --history prints it",
    )
    parser.add_argument(
        "--again",
        type=int,
        nargs="?",
        const=1,
        metavar="N",
        help="set the Nth most recent wallpaper again (default the last one)",
    )
    parser.add_argument(
        "--install-desktop",
        action="store_true",
        help="add corak to the application menu and exit",
    )
    parser.add_argument("--version", action="version", version=f"corak {__version__}")
    return parser


def _rotate_headless(design: str | None = None, recall: int | None = None) -> int:
    # No window is wanted, but QImage still needs a QGuiApplication, and the
    # offscreen plugin provides one without a display.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication

    QGuiApplication.instance() or QGuiApplication([])

    from .config import load
    from .rotation import describe, rotate
    from .store import Store
    from .wallpaper import WallpaperError

    from .design import Design

    try:
        with Store() as store:
            wanted = None
            if design is not None:
                wanted = Design.parse(design)
            elif recall is not None:
                wanted = _recall(store, recall)
            chosen, targets = rotate(load(), store=store, design=wanted)
    except (WallpaperError, ValueError, LookupError) as exc:
        print(f"corak: {exc}", file=sys.stderr)
        return 1
    print(describe(chosen, targets))
    return 0


def _recall(store, position: int):
    """The Nth most recent design, counting each one once.

    History holds a row per screen, so the last three rows are usually one
    wallpaper; counting rows would make "the one before last" mean "the same
    one, on another monitor".
    """
    if position < 1:
        raise ValueError("--again takes a position from 1")
    seen: list = []
    for entry in store.recent(position * 12):
        if entry.design not in seen:
            seen.append(entry.design)
        if len(seen) >= position:
            return seen[position - 1]
    raise LookupError(f"history holds only {len(seen)} design(s)")


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


def _list_themes() -> int:
    from .themes import BUILT_IN, all_themes

    # Compared by identity, not by id: an installed theme may share a name with
    # a packaged one, and it is the installed one on show. Theme holds a dict of
    # effects, so it is not hashable and cannot go in a set.
    packaged = [id(theme) for theme in BUILT_IN]
    for theme in all_themes():
        if theme.derived_from:
            origin = f"from {theme.derived_from}"
        else:
            origin = "built-in" if id(theme) in packaged else "installed"
        credit = (
            f"  [{theme.source}{', ' + theme.license if theme.license else ''}]"
            if theme.source
            else ""
        )
        print(f"{theme.id:<12} {theme.name:<16} {origin:<14} {theme.description}{credit}")
    return 0


def _add_theme(source: str) -> int:
    """Validate a theme document and install it for the user."""
    import json
    import shutil

    from .themes import Theme, problems, user_dir

    try:
        raw = sys.stdin.read() if source == "-" else open(source, encoding="utf-8").read()
        documents = json.loads(raw)
    except (OSError, ValueError) as exc:
        print(f"corak: {exc}", file=sys.stderr)
        return 1

    # A single theme or a list of them: a generated file is as likely to be one
    # as the other, and rejecting the wrong shape helps nobody.
    if isinstance(documents, dict):
        documents = [documents]
    if not isinstance(documents, list):
        print("corak: expected a theme object or a list of them", file=sys.stderr)
        return 1

    faults = False
    for document in documents:
        if not isinstance(document, dict):
            print(f"corak: not a theme: {document!r}", file=sys.stderr)
            faults = True
            continue
        found = problems(document)
        if found:
            name = document.get("id") or "<no id>"
            for problem in found:
                print(f"corak: {name}: {problem}", file=sys.stderr)
            faults = True
    if faults:
        return 1

    directory = user_dir()
    directory.mkdir(parents=True, exist_ok=True)
    for document in documents:
        theme = Theme.from_dict(document)
        path = directory / f"{theme.id}.json"
        path.write_text(json.dumps(document, indent=2) + "\n")
        print(f"installed {theme.name} -> {path}")
    return 0


def _install_desktop() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication

    QGuiApplication.instance() or QGuiApplication([])

    from .desktop import install
    from .scheduler import executable

    try:
        icon, entry = install(executable())
    except OSError as exc:
        print(f"corak: {exc}", file=sys.stderr)
        return 1
    print(f"installed {entry}\n          {icon}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.list_patterns:
        from .patterns import names

        print("\n".join(names()))
        return 0
    if args.history is not None:
        return _show_history(args.history)
    if args.list_themes:
        return _list_themes()
    if args.add_theme:
        return _add_theme(args.add_theme)
    if args.install_desktop:
        return _install_desktop()
    if args.design:
        return _rotate_headless(design=args.design)
    if args.again is not None:
        return _rotate_headless(recall=args.again)
    if args.next:
        return _rotate_headless()

    from .app import run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
