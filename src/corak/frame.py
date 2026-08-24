"""The surface a pattern draws on.

Carries physical density alongside pixel size so patterns can size features in
millimetres. Sizing by a fraction of the width instead makes the same design
render at wildly different apparent scales across a mixed set of monitors --
measured here, hexagons came out three times larger on the ultrawide than on the
portrait panel.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# 96 dpi, the conventional assumption when a display reports no usable size.
NOMINAL_PX_PER_MM = 96.0 / 25.4


@dataclass(frozen=True)
class Frame:
    width: int
    height: int
    px_per_mm: float = NOMINAL_PX_PER_MM
    # A theme-wide multiplier on every feature size, so a theme can read as
    # bold or as fine without each pattern needing a setting of its own.
    scale: float = 1.0

    @property
    def aspect(self) -> float:
        return self.width / self.height if self.height else 1.0

    @property
    def portrait(self) -> bool:
        return self.height > self.width

    @property
    def diagonal(self) -> float:
        return math.hypot(self.width, self.height)

    def mm(self, millimetres: float) -> float:
        """Millimetres as pixels on this surface, after the theme's scale."""
        return millimetres * self.px_per_mm * self.scale

    def count(self, millimetres: float, across: int | None = None) -> int:
        """How many features of the given size span the width, or the height."""
        span = across if across is not None else self.width
        return max(1, round(span / max(1.0, self.mm(millimetres))))
