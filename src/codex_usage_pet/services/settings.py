from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from .paths import config_path

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class AppSettings:
    window_x: int | None = None
    window_y: int | None = None
    opacity: float = 1.0
    refresh_interval: int = 60
    always_on_top: bool = True
    locked: bool = False
    show_usage: bool = True
    startup_enabled: bool = False

    def normalize(self) -> "AppSettings":
        self.opacity = max(0.4, min(1.0, float(self.opacity)))
        self.refresh_interval = max(30, min(900, int(self.refresh_interval)))
        self.always_on_top = bool(self.always_on_top)
        self.locked = bool(self.locked)
        self.show_usage = bool(self.show_usage)
        self.startup_enabled = bool(self.startup_enabled)
        if not isinstance(self.window_x, int):
            self.window_x = None
        if not isinstance(self.window_y, int):
            self.window_y = None
        return self


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or config_path()

    def load(self) -> AppSettings:
        if not self.path.exists():
            return AppSettings()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            allowed = {field.name for field in fields(AppSettings)}
            values = {key: value for key, value in raw.items() if key in allowed}
            return AppSettings(**values).normalize()
        except (OSError, ValueError, TypeError):
            LOGGER.warning("Configuration could not be read; defaults are active")
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        settings.normalize()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(asdict(settings), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)

