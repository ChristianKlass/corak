"""Installing the application into the desktop's menus.

Kept in-process rather than as a shell script so the launcher always points at
the interpreter that installed it, which is what makes a virtualenv checkout
work without a system-wide install.
"""

from __future__ import annotations

import os
import random
import shutil
import subprocess
from pathlib import Path

from .engine import Engine

ICON_NAME = "corak"
ICON_SIZE = 256
ENTRY_NAME = "corak.desktop"
# Fixed so the launcher icon does not change identity on every reinstall.
ICON_SEED = 0x2A5F13


def data_home() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base)


def icon_path() -> Path:
    return data_home() / "icons" / "hicolor" / f"{ICON_SIZE}x{ICON_SIZE}" / "apps" / f"{ICON_NAME}.png"


def entry_path() -> Path:
    return data_home() / "applications" / ENTRY_NAME


def entry_text(executable: str) -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=corak\n"
        "GenericName=Wallpaper Generator\n"
        "Comment=Procedurally generated geometric wallpapers\n"
        f"Exec={executable}\n"
        f"Icon={ICON_NAME}\n"
        "Terminal=false\n"
        "Categories=Graphics;Utility;\n"
        "Keywords=wallpaper;background;pattern;generator;\n"
        "StartupNotify=true\n"
        "StartupWMClass=corak\n"
    )


def write_icon(path: Path | None = None) -> Path:
    path = path or icon_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = Engine()
    design = engine.new_design(random.Random(ICON_SEED), pattern="hexagons")
    image = engine.render(design, ICON_SIZE, ICON_SIZE)
    if not image.save(str(path), "PNG"):
        raise OSError(f"could not write {path}")
    return path


def install(executable: str) -> tuple[Path, Path]:
    """Write the icon and menu entry. Returns both paths."""
    icon = write_icon()
    entry = entry_path()
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text(entry_text(executable))
    entry.chmod(0o755)

    if shutil.which("update-desktop-database"):
        # Failure here only delays the menu noticing; not worth reporting.
        subprocess.run(
            ["update-desktop-database", str(entry.parent)],
            capture_output=True,
            check=False,
            timeout=20,
        )
    return icon, entry
