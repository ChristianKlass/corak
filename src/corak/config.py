"""User settings, stored as JSON.

Unknown keys are ignored and missing ones fall back to defaults, so a settings
file written by a newer version does not stop an older one from starting.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, replace
from pathlib import Path

from .patterns import names

VERSION = 1
MIN_INTERVAL = 1
MAX_INTERVAL = 24 * 60


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "corak"


def settings_path() -> Path:
    return config_dir() / "settings.json"


@dataclass
class Settings:
    interval_minutes: int = 30
    patterns: list[str] = field(default_factory=names)
    effects: dict[str, float] = field(default_factory=lambda: {"calm": 0.7})
    keep: int = 12
    rotate: bool = False

    def normalised(self) -> "Settings":
        """Clamp to usable values, dropping anything no longer known."""
        known = set(names())
        patterns = [p for p in self.patterns if p in known]
        # Clamped before the zeroes are dropped: a negative strength is falsy
        # only after clamping, and would otherwise survive as a no-op entry.
        effects = {k: max(0.0, min(1.0, float(v))) for k, v in self.effects.items()}
        return replace(
            self,
            # An empty pattern list would leave nothing to generate, so it falls
            # back to everything rather than failing at the next rotation.
            patterns=patterns or names(),
            interval_minutes=max(MIN_INTERVAL, min(MAX_INTERVAL, int(self.interval_minutes))),
            effects={k: v for k, v in effects.items() if v > 0.0},
            keep=max(1, int(self.keep)),
        )

    def to_dict(self) -> dict:
        data = {"version": VERSION}
        data.update(self.normalised().__dict__)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        defaults = cls()
        return cls(
            interval_minutes=data.get("interval_minutes", defaults.interval_minutes),
            patterns=list(data.get("patterns", defaults.patterns)),
            effects=dict(data.get("effects", defaults.effects)),
            keep=data.get("keep", defaults.keep),
            rotate=bool(data.get("rotate", defaults.rotate)),
        ).normalised()


def load(path: Path | None = None) -> Settings:
    path = path or settings_path()
    try:
        return Settings.from_dict(json.loads(path.read_text()))
    except (OSError, ValueError, TypeError):
        # A corrupt or absent file is not worth refusing to start over.
        return Settings()


def save(settings: Settings, path: Path | None = None) -> Path:
    path = path or settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Written alongside and moved into place so an interrupted write cannot
    # leave a half-file that would silently reset every setting.
    temporary = path.with_suffix(".json.new")
    temporary.write_text(json.dumps(settings.to_dict(), indent=2) + "\n")
    temporary.replace(path)
    return path
