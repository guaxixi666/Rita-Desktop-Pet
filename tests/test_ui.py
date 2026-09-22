from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from codex_usage_pet.codex.rate_limits import parse_rate_limits
from codex_usage_pet.pet.states import PetState
from codex_usage_pet.services.settings import AppSettings, SettingsStore
from codex_usage_pet.services.startup import StartupManager
from codex_usage_pet.ui.pet_window import PetWindow


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def make_window(tmp_path: Path) -> PetWindow:
    return PetWindow(
        AppSettings(),
        SettingsStore(tmp_path / "settings.json"),
        StartupManager(registry=None),
    )


def test_window_is_frameless_tool_topmost_and_translucent(app, tmp_path: Path) -> None:
    window = make_window(tmp_path)
    flags = window.windowFlags()
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.Tool
    assert flags & Qt.WindowType.WindowStaysOnTopHint
    assert window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    window.deleteLater()


def test_snapshot_updates_bubble_and_pet_state(app, tmp_path: Path) -> None:
    window = make_window(tmp_path)
    snapshot = parse_rate_limits(
        {
            "rateLimits": {
                "primary": {"usedPercent": 95, "windowDurationMins": 300},
                "secondary": {"usedPercent": 50, "windowDurationMins": 10080},
            }
        }
    )
    window.set_snapshot(snapshot)
    assert window.pet.state is PetState.CRITICAL
    assert "快没粮" in window.bubble.status.text()
    assert "5%" in window.bubble.five_hour.detail.text()
    window.deleteLater()


def test_usage_visibility_is_saved(app, tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    window = PetWindow(AppSettings(), SettingsStore(path), StartupManager(registry=None))
    window.set_usage_visible(False)
    assert not window.bubble.isVisible()
    assert SettingsStore(path).load().show_usage is False
    window.deleteLater()

