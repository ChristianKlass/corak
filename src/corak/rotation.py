"""One rotation: pick a design, render it per screen, set it, record it."""

from __future__ import annotations

import random
from typing import Sequence

from .config import Settings
from .design import Design
from .engine import Engine
from .palette import Palette
from .store import Store
from .wallpaper import Target, prune, render_and_apply


def rotate(
    settings: Settings,
    engine: Engine | None = None,
    store: Store | None = None,
    design: Design | None = None,
    rng: random.Random | None = None,
    effects: dict[str, float] | None = None,
) -> tuple[Design, list[Target]]:
    settings = settings.normalised()
    theme = settings.active_theme()
    engine = engine or Engine(settings.patterns)
    engine.enabled = list(settings.patterns)
    engine.themes = tuple(settings.themes())
    if design is None:
        design = engine.new_design(rng or random.Random(), theme=theme)

    # The window passes its live effect toggles; a scheduled rotation takes the
    # theme's own.
    applied = theme.effects if effects is None else effects
    targets = render_and_apply(engine, design, applied)

    if store is not None:
        scheme = Palette.for_theme(
            design.palette_seed, theme, dark=True if applied.get("calm") else None
        ).scheme
        store.record(design, scheme, applied, targets)

    # Pruned here rather than inside render_and_apply so the history rows for
    # the deleted images go with them instead of accumulating forever.
    removed = prune(max(settings.keep, len(targets)))
    if store is not None and removed:
        store.forget(removed)
    return design, targets


def describe(design: Design, targets: Sequence[Target]) -> str:
    where = ", ".join(f"{t.screen.name} {t.screen.width}x{t.screen.height}" for t in targets)
    return f"{design} on {where}"
