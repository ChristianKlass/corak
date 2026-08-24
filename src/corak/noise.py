"""Coherent scalar fields.

Patterns look arbitrary when each cell picks a colour independently.  A cheap
sum-of-sines field gives neighbouring cells similar values, so colour drifts
across the image instead of flickering.  It is not Perlin noise and does not
need to be -- at wallpaper scale the difference is invisible.
"""

from __future__ import annotations

import math
from typing import Callable


def field(rng, terms: int = 3) -> Callable[[float, float], float]:
    """Return f(u, v) -> 0..1 for u, v in 0..1."""
    waves = []
    for _ in range(terms):
        angle = rng.uniform(0, math.tau)
        freq = rng.uniform(0.8, 3.2)
        waves.append(
            (math.cos(angle) * freq, math.sin(angle) * freq, rng.uniform(0, math.tau))
        )

    # Summed sines cancel far more often than they reinforce, so the raw mean
    # hugs the midpoint and every cell ends up the same colour. The gain pushes
    # the distribution back out toward both ends of the ramp.
    gain = 1.0 / (len(waves) * 0.62)

    def f(u: float, v: float) -> float:
        total = sum(math.sin(u * ax + v * ay + phase) for ax, ay, phase in waves)
        return min(1.0, max(0.0, (total * gain + 1.0) / 2.0))

    return f
