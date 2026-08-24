"""Setting the desktop background.

Each desktop shell is a separate backend because there is no shared mechanism:
Plasma takes a script over D-Bus, GNOME a pair of GSettings keys, and Xfce one
xfconf property per monitor.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from PySide6.QtGui import QImage

from .design import Design
from .screens import Screen


class WallpaperError(RuntimeError):
    pass


@dataclass(frozen=True)
class Target:
    """One rendered image and the screen it belongs on."""

    screen: Screen
    path: Path


def output_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "corak" / "wallpapers"


def save(image: QImage, design: Design, screen: Screen, directory: Path | None = None) -> Path:
    """Write a rendered image and return its path.

    Deliberately not a temporary file: desktop shells store the path in their
    own config and re-read it at every login, so an image that disappears takes
    the wallpaper with it.
    """
    directory = directory or output_dir()
    directory.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = directory / f"{stamp}-{screen.name}-{design.slug()}.png"
    if not image.save(str(path), "PNG"):
        raise WallpaperError(f"could not write {path}")
    return path


def prune(keep: int, directory: Path | None = None) -> list[str]:
    """Delete all but the newest `keep` images. Returns the paths removed.

    The caller needs the list: history rows point at these files, and without
    it the database keeps growing entries for images that no longer exist.
    """
    directory = directory or output_dir()
    if keep < 0 or not directory.is_dir():
        return []
    images = sorted(directory.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    removed = []
    for stale in images[keep:]:
        try:
            stale.unlink()
            removed.append(str(stale))
        except OSError:
            pass
    return removed


class Backend:
    name = "unknown"
    per_screen = False

    @staticmethod
    def matches(desktop: str) -> bool:
        return False

    def available(self) -> bool:
        return True

    def apply(self, targets: Sequence[Target]) -> None:
        raise NotImplementedError


def _run(argv: Sequence[str]) -> str:
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise WallpaperError(f"{argv[0]}: {exc}") from exc
    if done.returncode != 0:
        raise WallpaperError(f"{argv[0]} failed: {done.stderr.strip() or done.returncode}")
    return done.stdout


class PlasmaBackend(Backend):
    """KDE Plasma.

    `plasma-apply-wallpaperimage` can only set one image across every screen, so
    per-screen wallpapers go through the shell's own scripting interface, which
    can address each containment separately.
    """

    name = "plasma"
    per_screen = True

    @staticmethod
    def matches(desktop: str) -> bool:
        return "kde" in desktop or "plasma" in desktop

    def available(self) -> bool:
        return bool(os.environ.get("KDE_FULL_SESSION")) or shutil.which("plasmashell") is not None

    def _script(self, targets: Sequence[Target]) -> str:
        # Screens are matched by their logical top-left corner: Plasma numbers
        # containments by its own screen index, which need not agree with Qt's
        # ordering, but the positions are the same in both.
        by_position = {f"{t.screen.x},{t.screen.y}": str(t.path) for t in targets}
        return (
            "var byPosition = %s;\n"
            "var all = desktops();\n"
            "for (var i = 0; i < all.length; i++) {\n"
            "    var d = all[i];\n"
            "    var g = screenGeometry(d.screen);\n"
            "    var file = byPosition[g.x + ',' + g.y];\n"
            "    if (!file) continue;\n"
            "    d.wallpaperPlugin = 'org.kde.image';\n"
            "    d.currentConfigGroup = ['Wallpaper', 'org.kde.image', 'General'];\n"
            "    d.writeConfig('Image', 'file://' + file);\n"
            "    d.writeConfig('FillMode', 2);\n"
            "    d.reloadConfig();\n"
            "}\n" % json.dumps(by_position)
        )

    def apply(self, targets: Sequence[Target]) -> None:
        if not targets:
            return
        try:
            self._evaluate(self._script(targets))
        except WallpaperError:
            # Losing per-screen placement beats leaving the wallpaper unchanged.
            self._apply_single(targets)

    def _evaluate(self, script: str) -> None:
        from PySide6.QtDBus import QDBusConnection, QDBusInterface

        bus = QDBusConnection.sessionBus()
        if not bus.isConnected():
            raise WallpaperError("no session bus")
        shell = QDBusInterface("org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell", bus)
        if not shell.isValid():
            raise WallpaperError("plasmashell is not on the session bus")
        reply = shell.call("evaluateScript", script)
        error = reply.errorMessage()
        if error:
            raise WallpaperError(f"plasma script rejected: {error}")

    def _apply_single(self, targets: Sequence[Target]) -> None:
        if shutil.which("plasma-apply-wallpaperimage") is None:
            raise WallpaperError("plasma scripting failed and plasma-apply-wallpaperimage is missing")
        primary = next((t for t in targets if t.screen.primary), targets[0])
        _run(["plasma-apply-wallpaperimage", str(primary.path)])


class GnomeBackend(Backend):
    """GNOME, and shells that follow its GSettings schema."""

    name = "gnome"
    per_screen = False

    @staticmethod
    def matches(desktop: str) -> bool:
        return any(token in desktop for token in ("gnome", "unity", "cinnamon"))

    def available(self) -> bool:
        return shutil.which("gsettings") is not None

    def apply(self, targets: Sequence[Target]) -> None:
        if not targets:
            return
        primary = next((t for t in targets if t.screen.primary), targets[0])
        uri = primary.path.as_uri()
        for key in ("picture-uri", "picture-uri-dark"):
            # picture-uri-dark only exists from GNOME 42 on; on older versions
            # the light key alone is the whole setting.
            try:
                _run(["gsettings", "set", "org.gnome.desktop.background", key, uri])
            except WallpaperError:
                if key == "picture-uri":
                    raise
        _run(["gsettings", "set", "org.gnome.desktop.background", "picture-options", "zoom"])


class XfceBackend(Backend):
    """Xfce, which stores one image path per monitor and workspace."""

    name = "xfce"
    per_screen = True

    @staticmethod
    def matches(desktop: str) -> bool:
        return "xfce" in desktop

    def available(self) -> bool:
        return shutil.which("xfconf-query") is not None

    def _image_properties(self) -> list[str]:
        listing = _run(["xfconf-query", "-c", "xfce4-desktop", "-l"])
        return [line.strip() for line in listing.splitlines() if line.strip().endswith("last-image")]

    def apply(self, targets: Sequence[Target]) -> None:
        if not targets:
            return
        properties = self._image_properties()
        if not properties:
            raise WallpaperError("xfce4-desktop has no last-image properties")
        primary = next((t for t in targets if t.screen.primary), targets[0])
        for prop in properties:
            # The property path carries the monitor name, so a screen's own
            # image is used where the name matches and the primary elsewhere.
            match = next((t for t in targets if f"monitor{t.screen.name}/" in prop), primary)
            _run(["xfconf-query", "-c", "xfce4-desktop", "-p", prop, "-s", str(match.path)])


BACKENDS: tuple[type[Backend], ...] = (PlasmaBackend, GnomeBackend, XfceBackend)


def current_desktop() -> str:
    return (
        os.environ.get("XDG_CURRENT_DESKTOP")
        or os.environ.get("XDG_SESSION_DESKTOP")
        or os.environ.get("DESKTOP_SESSION")
        or ""
    ).lower()


def detect_backend(desktop: str | None = None) -> Backend:
    desktop = current_desktop() if desktop is None else desktop.lower()
    for backend in BACKENDS:
        if backend.matches(desktop):
            return backend()
    raise WallpaperError(
        f"unsupported desktop: {desktop or 'none reported'} "
        f"(known: {', '.join(b.name for b in BACKENDS)})"
    )


def render_and_apply(
    engine,
    design: Design,
    effects=None,
    screens: Sequence[Screen] | None = None,
    keep: int | None = None,
    backend: Backend | None = None,
) -> list[Target]:
    """Render the design at each screen's native size and set it as wallpaper.

    Backends that cannot address screens individually still get one image, so
    nothing renders needlessly on GNOME.
    """
    from .screens import detect

    backend = backend or detect_backend()
    if not backend.available():
        raise WallpaperError(f"{backend.name} backend is not usable in this session")

    screens = list(screens if screens is not None else detect())
    if not screens:
        raise WallpaperError("no screens detected")
    if not backend.per_screen:
        screens = [next((s for s in screens if s.primary), screens[0])]

    targets = [
        Target(
            screen,
            save(
                # Millimetres, not a fraction of the width, so a design keeps its
                # apparent scale across displays of differing density.
                engine.render(design, screen.width, screen.height, effects, screen.px_per_mm),
                design,
                screen,
            ),
        )
        for screen in screens
    ]
    backend.apply(targets)
    if keep is not None:
        # Pruned after applying so the images still in use are the newest ones
        # and cannot be deleted out from under the desktop.
        prune(max(keep, len(targets)))
    return targets
