"""The four arrow-key actions, kept out of the UI so they can be tested."""

from __future__ import annotations

import random

from .design import Design, History
from .engine import Engine


class Session:
    def __init__(self, engine: Engine, rng: random.Random | None = None) -> None:
        self.engine = engine
        self.rng = rng or random.Random()
        self.history = History()
        self._set(self.engine.new_design(self.rng))

    def _set(self, design: Design) -> Design:
        self.history.push(design)
        return design

    @property
    def current(self) -> Design:
        design = self.history.current
        assert design is not None  # the constructor always seeds one
        return design

    def regenerate(self) -> Design:
        """Up: a new pattern and a new palette."""
        return self._set(self.engine.new_design(self.rng))

    def recolour(self) -> Design:
        """Left: same pattern and geometry, new colours."""
        current = self.current
        return self._set(
            Design(current.pattern, current.pattern_seed, self.rng.randrange(1 << 24))
        )

    def repattern(self) -> Design:
        """Right: same colours, a new pattern."""
        current = self.current
        choices = [p for p in self.engine.enabled if p != current.pattern]
        # With a single pattern enabled there is nothing to switch to, so reroll
        # its geometry instead of silently doing nothing.
        pattern = self.rng.choice(choices) if choices else current.pattern
        return self._set(
            self.engine.new_design(self.rng, pattern=pattern, palette_seed=current.palette_seed)
        )

    def previous(self) -> Design | None:
        """Down: step back through what has already been seen."""
        return self.history.back()
