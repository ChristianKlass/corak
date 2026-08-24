"""What fully describes one wallpaper.

Pattern and palette carry separate seeds on purpose: the Left arrow recolours
without disturbing the geometry, and the Right arrow does the reverse.  A single
seed could not express either, and would make history entries unreproducible.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Design:
    pattern: str
    pattern_seed: int
    palette_seed: int
    # Part of the identity, not a setting: the same seeds under a different
    # theme are a different image, so a history row without it is not
    # reproducible.
    theme: str = ""

    def slug(self) -> str:
        stem = f"{self.pattern}-{self.pattern_seed:06x}-{self.palette_seed:06x}"
        return f"{self.theme}-{stem}" if self.theme else stem

    def __str__(self) -> str:
        return self.slug()


class History:
    """A linear back-stack. Down walks toward older designs."""

    def __init__(self, limit: int = 200) -> None:
        self._items: list[Design] = []
        self._cursor = -1
        self._limit = limit

    def push(self, design: Design) -> None:
        # A new design truncates anything the cursor had walked back past, so
        # the stack always reads as the path actually taken.
        del self._items[self._cursor + 1 :]
        self._items.append(design)
        if len(self._items) > self._limit:
            del self._items[0]
        self._cursor = len(self._items) - 1

    def back(self) -> Design | None:
        if self._cursor <= 0:
            return None
        self._cursor -= 1
        return self._items[self._cursor]

    def forward(self) -> Design | None:
        if self._cursor >= len(self._items) - 1:
            return None
        self._cursor += 1
        return self._items[self._cursor]

    @property
    def current(self) -> Design | None:
        return self._items[self._cursor] if self._items else None

    def __len__(self) -> int:
        return len(self._items)
