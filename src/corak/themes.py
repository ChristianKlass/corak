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

from dataclasses import asdict, dataclass, field, replace
from typing import Sequence

from .palette import SCHEMES

DEFAULT_ID = "quiet"


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
    derived_from: str = ""

    @property
    def built_in(self) -> bool:
        return not self.derived_from

    def derive(self, **changes) -> "Theme":
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
        data["lightness"] = list(self.lightness) if self.lightness else None
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Theme":
        base = cls(id=str(data.get("id", "")), name=str(data.get("name", "")))
        hue = data.get("hue_range")
        chroma = data.get("chroma") or base.chroma
        lightness = data.get("lightness")
        return replace(
            base,
            description=str(data.get("description", "")),
            patterns=tuple(data.get("patterns") or ()),
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
            derived_from=str(data.get("derived_from", "")),
        )


BUILT_IN: tuple[Theme, ...] = (
    Theme(
        id="quiet",
        name="Quiet",
        description="Dark and barely there. Made to sit behind windows.",
        schemes=("mono", "analogous"),
        chroma=(0.025, 0.07),
        dark=True,
        effects={"calm": 0.7},
        scale=1.3,
    ),
    Theme(
        id="slate",
        name="Slate",
        description="Almost colourless, large shapes, very low contrast.",
        patterns=("hexagons", "triangles"),
        schemes=("mono",),
        chroma=(0.008, 0.032),
        dark=True,
        effects={"calm": 0.55},
        scale=1.7,
    ),
    Theme(
        id="ember",
        name="Ember",
        description="Reds through amber, dark, with the edges falling away.",
        schemes=("mono", "analogous"),
        hue_range=(0.94, 1.14),
        chroma=(0.09, 0.17),
        dark=True,
        effects={"calm": 0.4, "vignette": 0.5},
    ),
    Theme(
        id="tide",
        name="Tide",
        description="Cool blues and teals, softly graded.",
        schemes=("analogous", "split"),
        hue_range=(0.47, 0.63),
        chroma=(0.07, 0.14),
        dark=True,
        effects={"calm": 0.45},
        scale=1.15,
    ),
    Theme(
        id="linen",
        name="Linen",
        description="Soft and muted. Lighter than the rest without lighting up the room.",
        schemes=("mono", "analogous"),
        # Everything except roughly 0.12 to 0.45 of a turn, which is where the
        # khaki lives at these lightnesses. The range wraps past red, and stops
        # clear of the boundary rather than resting on it.
        hue_range=(0.45, 1.12),
        chroma=(0.03, 0.07),
        lightness=(0.52, 0.72),
        dark=False,
        effects={"calm": 0.2},
        scale=0.95,
    ),
    Theme(
        id="signal",
        name="Signal",
        description="Loud. Full chroma, opposing hues, nothing held back.",
        schemes=("complement", "split", "triad"),
        chroma=(0.13, 0.21),
        dark=True,
        effects={},
        scale=0.8,
    ),
)

BY_ID: dict[str, Theme] = {theme.id: theme for theme in BUILT_IN}


def get(identifier: str, extra: Sequence[Theme] = ()) -> Theme:
    """Look up a theme by id, falling back to the default rather than failing.

    A settings file naming a theme that has since been deleted should not stop
    the wallpaper rotating.
    """
    for theme in extra:
        if theme.id == identifier:
            return theme
    return BY_ID.get(identifier) or BY_ID[DEFAULT_ID]


def all_themes(extra: Sequence[Theme] = ()) -> list[Theme]:
    return list(BUILT_IN) + [t for t in extra if t.id not in BY_ID]
