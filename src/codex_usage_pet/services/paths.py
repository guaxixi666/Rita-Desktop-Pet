from __future__ import annotations

import os
import sys
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


def resource_path(relative: str) -> Path:
    """Resolve a project asset in source and in a PyInstaller bundle."""
    if getattr(sys, "frozen", False):
        root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        root = Path(__file__).resolve().parents[3]
    return root / relative

