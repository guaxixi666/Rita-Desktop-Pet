from __future__ import annotations

import os
from pathlib import Path


def app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "CodexUsagePet"
    return Path.home() / ".codex-usage-pet"


def config_path() -> Path:
    return app_data_dir() / "config.json"


def log_dir() -> Path:
    return app_data_dir() / "logs"

