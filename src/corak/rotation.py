"""One rotation: pick a design, render it per screen, set it, record it."""

from __future__ import annotations

import random
from typing import Sequence

from .config import Settings
from .design import Design
from .engine import Engine
from .palette import Palette
from .store import Store
from .wallpaper import Target, render_and_apply


def rotate(
    settings: Settings,
    engine: Engine | None = None,
    store: Store | None = None,
    design: Design | None = None,
    rng: random.Random | None = None,
) -> tuple[Design, list[Target]]:
    settings = settings.normalised()
    engine = engine or Engine(settings.patterns)
    engine.enabled = list(settings.patterns)
    if design is None:
        design = engine.new_design(rng or random.Random())

    targets = render_and_apply(engine, design, settings.effects, keep=settings.keep)

    if store is not None:
        scheme = Palette(design.palette_seed, dark=True if settings.effects.get("calm") else None).scheme
        store.record(design, scheme, settings.effects, targets)
    return design, targets


def describe(design: Design, targets: Sequence[Target]) -> str:
    where = ", ".join(f"{t.screen.name} {t.screen.width}x{t.screen.height}" for t in targets)
    return f"{design} on {where}"
