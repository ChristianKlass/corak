"""A record of everything generated.

Stores what a design was rather than the image itself: a row is enough to
rebuild the wallpaper exactly, which is the point of keeping the geometry and
colour seeds apart.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from .design import Design

SCHEMA = """
CREATE TABLE IF NOT EXISTS designs (
    id            INTEGER PRIMARY KEY,
    created_at    TEXT    NOT NULL,
    pattern       TEXT    NOT NULL,
    pattern_seed  INTEGER NOT NULL,
    palette_seed  INTEGER NOT NULL,
    theme         TEXT,
    scheme        TEXT,
    effects       TEXT,
    screen        TEXT,
    width         INTEGER,
    height        INTEGER,
    path          TEXT
);
CREATE INDEX IF NOT EXISTS designs_created_at ON designs (created_at DESC);
"""


def data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "corak"


def database_path() -> Path:
    return data_dir() / "history.db"


@dataclass(frozen=True)
class Entry:
    created_at: str
    design: Design
    scheme: str
    effects: dict[str, float]
    screen: str
    width: int
    height: int
    path: str


class Store:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or database_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(self.path))
        self._connection.executescript(SCHEMA)
        self._migrate()
        self._connection.commit()

    def _migrate(self) -> None:
        """Add columns a database written by an earlier version is missing."""
        existing = {row[1] for row in self._connection.execute("PRAGMA table_info(designs)")}
        for column, definition in (("theme", "TEXT"),):
            if column not in existing:
                self._connection.execute(f"ALTER TABLE designs ADD COLUMN {column} {definition}")

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def record(
        self,
        design: Design,
        scheme: str,
        effects: dict[str, float],
        targets: Sequence,
    ) -> int:
        """Add one row per screen the design was rendered for."""
        created_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        payload = json.dumps(effects, sort_keys=True)
        rows = [
            (
                created_at,
                design.pattern,
                design.pattern_seed,
                design.palette_seed,
                design.theme,
                scheme,
                payload,
                target.screen.name,
                target.screen.width,
                target.screen.height,
                str(target.path),
            )
            for target in targets
        ]
        with self._connection:
            self._connection.executemany(
                "INSERT INTO designs (created_at, pattern, pattern_seed, palette_seed,"
                " theme, scheme, effects, screen, width, height, path)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
        return len(rows)

    def recent(self, limit: int = 20) -> list[Entry]:
        cursor = self._connection.execute(
            "SELECT created_at, pattern, pattern_seed, palette_seed, theme, scheme,"
            " effects, screen, width, height, path FROM designs ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [
            Entry(
                created_at=row[0],
                design=Design(row[1], row[2], row[3], row[4] or ""),
                scheme=row[5] or "",
                effects=json.loads(row[6]) if row[6] else {},
                screen=row[7] or "",
                width=row[8] or 0,
                height=row[9] or 0,
                path=row[10] or "",
            )
            for row in cursor
        ]

    def count(self) -> int:
        return int(self._connection.execute("SELECT COUNT(*) FROM designs").fetchone()[0])

    def forget(self, paths: Iterable[str]) -> int:
        """Clear the file path on rows whose images have been deleted.

        The row survives. A design is reproducible from its seeds, so it can
        still be recalled long after the image it produced was pruned -- and
        deleting the row instead meant history reached back only as far as the
        dozen images kept on disk.
        """
        paths = list(paths)
        if not paths:
            return 0
        with self._connection:
            cursor = self._connection.executemany(
                "UPDATE designs SET path = '' WHERE path = ?", [(p,) for p in paths]
            )
        return cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0
