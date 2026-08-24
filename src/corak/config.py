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
from .themes import DEFAULT_ID, Theme, all_themes, get

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
    # Effects, colours and scale belong to the theme; what stays here is what
    # applies across every theme.
    theme: str = DEFAULT_ID
    custom_themes: list[dict] = field(default_factory=list)
    keep: int = 12
    rotate: bool = False

    def themes(self) -> list[Theme]:
        """User-derived themes, skipping any that no longer parse."""
        built = []
        for data in self.custom_themes:
            try:
                theme = Theme.from_dict(data)
            except (TypeError, ValueError, KeyError, IndexError):
                continue
            if theme.id:
                built.append(theme)
        return built

    def active_theme(self) -> Theme:
        return get(self.theme, self.themes())

    def with_theme(self, theme: Theme) -> Settings:
        """Store a derived theme and make it active, replacing any namesake."""
        others = [t for t in self.custom_themes if t.get("id") != theme.id]
        return replace(
            self,
            theme=theme.id,
            custom_themes=([*others, theme.to_dict()]) if not theme.built_in else others,
        )

    def normalised(self) -> Settings:
        """Clamp to usable values, dropping anything no longer known."""
        known = set(names())
        patterns = [p for p in self.patterns if p in known]
        available = {t.id for t in all_themes(self.themes())}
        return replace(
            self,
            # An empty pattern list would leave nothing to generate, so it falls
            # back to everything rather than failing at the next rotation.
            patterns=patterns or names(),
            interval_minutes=max(MIN_INTERVAL, min(MAX_INTERVAL, int(self.interval_minutes))),
            # A theme that has since been deleted must not stop the rotation.
            theme=self.theme if self.theme in available else DEFAULT_ID,

            keep=max(1, int(self.keep)),
        )

    def to_dict(self) -> dict:
        data = {"version": VERSION}
        data.update(self.normalised().__dict__)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> Settings:
        defaults = cls()
        return cls(
            interval_minutes=data.get("interval_minutes", defaults.interval_minutes),
            patterns=list(data.get("patterns", defaults.patterns)),
            theme=str(data.get("theme", defaults.theme)),
            custom_themes=list(data.get("custom_themes", [])),
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
