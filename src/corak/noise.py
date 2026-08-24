"""Coherent scalar fields.

Patterns look arbitrary when each cell picks a colour independently. A cheap
sum-of-sines field gives neighbouring cells similar values, so colour drifts
across the image instead of flickering. It is not Perlin noise and does not need
to be -- at wallpaper scale the difference is invisible.

Fields are evaluated over the unit square and normalised to actually span 0 to
1 across it. Without that a low-frequency field completes less than one cycle
over the image, which leaves it near-constant at whatever value its phases
happen to give -- often pinned to one end, so every shape takes the same colour.
"""

from __future__ import annotations

import math
from collections.abc import Callable

SAMPLES = 17


def field(rng, terms: int = 3, frequency: float = 1.0) -> Callable[[float, float], float]:
    """Return f(u, v) -> 0..1, for u and v in 0..1.

    `frequency` sets how much the value changes across the image: below 1 it
    drifts, above 1 it varies within a small neighbourhood.
    """
    waves = []
    for _ in range(terms):
        angle = rng.uniform(0, math.tau)
        rate = rng.uniform(0.8, 3.2) * frequency * math.tau
        waves.append((math.cos(angle) * rate, math.sin(angle) * rate, rng.uniform(0, math.tau)))

    def raw(u: float, v: float) -> float:
        return sum(math.sin(u * ax + v * ay + phase) for ax, ay, phase in waves)

    # Measured rather than assumed: summed sines cancel more often than they
    # reinforce, so the theoretical range is nothing like the observed one.
    seen = [
        raw(i / (SAMPLES - 1), j / (SAMPLES - 1))
        for i in range(SAMPLES)
        for j in range(SAMPLES)
    ]
    low, high = min(seen), max(seen)
    span = high - low
    if span < 1e-6:
        return lambda u, v: 0.5

    def f(u: float, v: float) -> float:
        return min(1.0, max(0.0, (raw(u, v) - low) / span))

    return f
