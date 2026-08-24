"""Themes: a set of constraints that generate many similar wallpapers.

A theme is not one wallpaper and not a free-for-all. It pins the things that
give a wallpaper its character -- which patterns, which part of the colour
wheel, how saturated, how large the shapes, which effects -- and leaves the rest
to the seed. Every image it produces is different; they all look related.

Built-in themes are the starting points. Rather than building one from nothing,
which means answering a dozen questions before seeing anything, a theme is
changed by deriving from one that already works.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field, replace
from importlib import resources
from pathlib import Path

from PySide6.QtGui import QColor

from .palette import SCHEMES

DEFAULT_ID = "nightfall"

# A theme id is used as a filename, so it may not contain a path.
SAFE_ID = re.compile(r"[a-z0-9][a-z0-9_-]*")


@dataclass(frozen=True)
class Theme:
    id: str
    name: str
    description: str = ""
    # Empty means "no constraint": every pattern, the default scheme weights.
    patterns: tuple[str, ...] = ()
    schemes: tuple[str, ...] = ()
    # In turns. The end may exceed 1.0 to describe a range that wraps past red.
    hue_range: tuple[float, float] | None = None
    # Explicit colours, as hex. Given these, the hue and chroma ranges are
    # ignored: the palette is the one supplied rather than one generated.
    colors: tuple[str, ...] = ()
    chroma: tuple[float, float] = (0.045, 0.16)
    # Perceptual lightness the ramp spans. Left unset it follows `dark`.
    lightness: tuple[float, float] | None = None
    dark: bool | None = None
    effects: dict[str, float] = field(default_factory=dict)
    # Multiplies every feature size, so a theme can read as bold or as fine
    # without each pattern needing its own setting.
    scale: float = 1.0
    # Gradient and shadow strength, 0 for flat fills.
    depth: float = 1.0
    # Where a palette came from, when it was not made here, and under what
    # terms. Colour values are not the licensable part -- the attribution is a
    # courtesy to the people who chose them, and to anyone redistributing this.
    source: str = ""
    license: str = ""
    derived_from: str = ""

    @property
    def built_in(self) -> bool:
        return not self.derived_from

    def derive(self, **changes) -> Theme:
        """A variant of this theme, keeping everything not named."""
        identifier = changes.pop("id", None) or f"{self.id}-custom"
        name = changes.pop("name", None) or f"{self.name} (modified)"
        return replace(
            self,
            id=identifier,
            name=name,
            derived_from=self.derived_from or self.id,
            **changes,
        )

    def to_dict(self) -> dict:
        data = asdict(self)
        data["patterns"] = list(self.patterns)
        data["schemes"] = list(self.schemes)
        data["hue_range"] = list(self.hue_range) if self.hue_range else None
        data["chroma"] = list(self.chroma)
        data["colors"] = list(self.colors)
        data["lightness"] = list(self.lightness) if self.lightness else None
        return data

    @classmethod
    def from_dict(cls, data: dict) -> Theme:
        base = cls(id=str(data.get("id", "")), name=str(data.get("name", "")))
        hue = data.get("hue_range")
        chroma = data.get("chroma") or base.chroma
        lightness = data.get("lightness")
        return replace(
            base,
            description=str(data.get("description", "")),
            patterns=tuple(data.get("patterns") or ()),
            colors=tuple(str(c) for c in (data.get("colors") or ())),
            schemes=tuple(s for s in (data.get("schemes") or ()) if s in SCHEMES),
            hue_range=(float(hue[0]), float(hue[1])) if hue else None,
            chroma=(float(chroma[0]), float(chroma[1])),
            lightness=(float(lightness[0]), float(lightness[1])) if lightness else None,
            dark=data.get("dark"),
            # Clamped before the zeroes go, so a negative strength -- falsy only
            # after clamping -- cannot survive as a no-op entry.
            effects={
                k: v
                for k, v in (
                    (k, max(0.0, min(1.0, float(v))))
                    for k, v in (data.get("effects") or {}).items()
                )
                if v > 0.0
            },
            scale=float(data.get("scale", 1.0)),
            depth=float(data.get("depth", 1.0)),
            source=str(data.get("source", "")),
            license=str(data.get("license", "")),
            derived_from=str(data.get("derived_from", "")),
        )


def _load_packaged() -> tuple[Theme, ...]:
    """Read the built-in themes from the JSON shipped beside this module.

    Kept as data rather than code so a theme can come from anywhere -- hand
    written, exported from the app, or generated somewhere else entirely -- and
    so tuning one is not a source change.
    """
    directory = resources.files(__package__) / "data" / "themes"
    themes = []
    for entry in sorted(directory.iterdir(), key=lambda e: e.name):
        if not entry.name.endswith(".json"):
            continue
        try:
            theme = Theme.from_dict(json.loads(entry.read_text()))
        except (OSError, ValueError, TypeError, KeyError, IndexError):
            # One unreadable file must not take the whole set down with it.
            continue
        if theme.id:
            themes.append(theme)
    return tuple(themes)


def user_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "corak" / "themes"


def _load_directory(directory: Path) -> list[Theme]:
    if not directory.is_dir():
        return []
    themes = []
    for entry in sorted(directory.glob("*.json")):
        try:
            theme = Theme.from_dict(json.loads(entry.read_text()))
        except (OSError, ValueError, TypeError, KeyError, IndexError):
            continue
        if theme.id:
            themes.append(theme)
    return themes


def user_themes() -> list[Theme]:
    """Themes dropped into the config directory, from wherever they came."""
    return _load_directory(user_dir())


BUILT_IN: tuple[Theme, ...] = _load_packaged()

BY_ID: dict[str, Theme] = {theme.id: theme for theme in BUILT_IN}


def get(identifier: str, extra: Sequence[Theme] = ()) -> Theme:
    """Look up a theme by id, falling back to the default rather than failing.

    A settings file naming a theme that has since been deleted should not stop
    the wallpaper rotating.
    """
    for theme in list(extra) + user_themes():
        if theme.id == identifier:
            return theme
    if identifier in BY_ID:
        return BY_ID[identifier]
    # A default that has itself been removed should still not raise.
    return BY_ID.get(DEFAULT_ID) or (BUILT_IN[0] if BUILT_IN else Theme("none", "None"))


def all_themes(extra: Sequence[Theme] = ()) -> list[Theme]:
    """Every theme available, installed ones shadowing packaged namesakes.

    An installed theme wins: someone who writes a file called slate.json means
    to replace slate, and `get` resolves it that way, so the listing has to
    agree or the two disagree about what a name refers to.
    """
    by_id = {theme.id: theme for theme in BUILT_IN}
    for theme in user_themes() + list(extra):
        by_id[theme.id] = theme
    order = [t.id for t in BUILT_IN]
    order += [i for i in by_id if i not in order]
    return [by_id[i] for i in order]


def problems(data: dict) -> list[str]:
    """Everything wrong with a theme document, in plain words.

    Returned rather than raised: a file written elsewhere is worth reporting on
    in full instead of one complaint at a time.
    """
    found = []
    identifier = str(data.get("id", "")).strip()
    if not identifier:
        found.append("needs an id")
    elif not SAFE_ID.fullmatch(identifier):
        # The id becomes a filename. Left unchecked, "../../x" or "/etc/x"
        # writes wherever the person running this can write, which turns
        # installing a theme somebody sent you into arbitrary file creation.
        found.append(
            "id must be lowercase letters, digits, hyphens or underscores"
        )
    if not str(data.get("name", "")).strip():
        found.append("needs a name")

    for key, limit in (("chroma", 0.4), ("lightness", 1.0)):
        value = data.get(key)
        if value is None:
            continue
        if not (isinstance(value, (list, tuple)) and len(value) == 2) or not all(isinstance(v, (int, float)) for v in value):
            found.append(f"{key} must be two numbers")
        elif value[0] > value[1]:
            found.append(f"{key} runs backwards")
        elif not (value[0] >= 0.0 and value[1] <= limit):
            found.append(f"{key} must lie between 0 and {limit}")

    hue = data.get("hue_range")
    if hue is not None:
        if not (isinstance(hue, (list, tuple)) and len(hue) == 2):
            found.append("hue_range must be two numbers")
        elif hue[0] > hue[1]:
            found.append("hue_range runs backwards")
        elif hue[1] - hue[0] > 1.0:
            found.append("hue_range covers more than the whole wheel")

    colors = data.get("colors") or ()
    if not isinstance(colors, (list, tuple)):
        found.append("colors must be a list of hex codes")
    else:
        for code in colors:
            if not isinstance(code, str) or not QColor(
                code if str(code).startswith("#") else f"#{code}"
            ).isValid():
                found.append(f"not a colour: {code}")
        if colors and len(colors) < 2:
            found.append("colors needs at least two entries")

    unknown = [s for s in (data.get("schemes") or ()) if s not in SCHEMES]
    if unknown:
        found.append(f"unknown schemes: {', '.join(map(str, unknown))} "
                     f"(known: {', '.join(sorted(SCHEMES))})")

    for key in ("scale", "depth"):
        value = data.get(key, 1.0)
        if not isinstance(value, (int, float)) or not 0.0 <= value <= 4.0:
            found.append(f"{key} must be a number between 0 and 4")

    effects = data.get("effects") or {}
    if not isinstance(effects, dict):
        found.append("effects must be a mapping of name to strength")
    else:
        for name, strength in effects.items():
            if not isinstance(strength, (int, float)) or not 0.0 <= strength <= 1.0:
                found.append(f"effect {name} must be between 0 and 1")
    return found
