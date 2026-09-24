from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from .paths import config_path

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class AppSettings:
    window_x: int | None = None
    window_y: int | None = None
    pet_anchor_x: int | None = None
    pet_anchor_y: int | None = None
    opacity: float = 1.0
    refresh_interval: int = 60
    always_on_top: bool = True
    locked: bool = False
    show_usage: bool = True
    startup_enabled: bool = False
    current_skin: str = "rita_umbral_rose"
    auto_skin_enabled: bool = False
    auto_skin_mode: str = "off"
    auto_skin_interval_hours: int = 24
    auto_skin_fixed_time: str = "08:00"
    last_skin_change: str | None = None
    random_skin_no_repeat: bool = True
    action_pool_overrides: dict[str, dict[str, list[str]]] = field(default_factory=dict)

    def normalize(self) -> "AppSettings":
        self.opacity = max(0.4, min(1.0, float(self.opacity)))
        self.refresh_interval = max(30, min(900, int(self.refresh_interval)))
        self.always_on_top = bool(self.always_on_top)
        self.locked = bool(self.locked)
        self.show_usage = bool(self.show_usage)
        self.startup_enabled = bool(self.startup_enabled)
        self.current_skin = str(self.current_skin or "rita_umbral_rose")
        self.auto_skin_enabled = bool(self.auto_skin_enabled)
        if self.auto_skin_mode not in {"off", "interval", "fixed_time"}:
            self.auto_skin_mode = "off"
        self.auto_skin_interval_hours = max(1, min(24 * 30, int(self.auto_skin_interval_hours)))
        try:
            hours, minutes = (int(part) for part in self.auto_skin_fixed_time.split(":"))
            if not (0 <= hours <= 23 and 0 <= minutes <= 59):
                raise ValueError
            self.auto_skin_fixed_time = f"{hours:02d}:{minutes:02d}"
        except (AttributeError, TypeError, ValueError):
            self.auto_skin_fixed_time = "08:00"
        if self.last_skin_change is not None and not isinstance(self.last_skin_change, str):
            self.last_skin_change = None
        self.random_skin_no_repeat = bool(self.random_skin_no_repeat)
        normalized_overrides: dict[str, dict[str, list[str]]] = {}
        if isinstance(self.action_pool_overrides, dict):
            for skin_id, raw_pools in self.action_pool_overrides.items():
                if not isinstance(raw_pools, dict):
                    continue
                pools: dict[str, list[str]] = {}
                for event, raw_actions in raw_pools.items():
                    if not isinstance(raw_actions, list):
                        continue
                    actions = [str(action).strip().lower() for action in raw_actions]
                    pools[str(event)] = list(dict.fromkeys(action for action in actions if action))
                normalized_overrides[str(skin_id)] = pools
        self.action_pool_overrides = normalized_overrides
        if not isinstance(self.window_x, int):
            self.window_x = None
        if not isinstance(self.window_y, int):
            self.window_y = None
        if not isinstance(self.pet_anchor_x, int):
            self.pet_anchor_x = None
        if not isinstance(self.pet_anchor_y, int):
            self.pet_anchor_y = None
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

