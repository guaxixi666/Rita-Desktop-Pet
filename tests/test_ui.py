from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from codex_usage_pet.codex.rate_limits import parse_rate_limits
from codex_usage_pet.pet.animator import PetActivity
from codex_usage_pet.pet.states import PetState
from codex_usage_pet.services.settings import AppSettings, SettingsStore
from codex_usage_pet.services.startup import StartupManager
from codex_usage_pet.ui.pet_window import PetWindow
from codex_usage_pet.ui.tray import TrayIcon


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
    assert window.pet.sprite_loaded
    window.deleteLater()


def test_rita_sprite_sheet_has_transparent_cells() -> None:
    image = QImage(
        str(
            Path(__file__).parents[1]
            / "skins"
            / "rita_umbral_rose"
            / "rita_sprite_sheet.png"
        )
    )
    assert not image.isNull()
    assert image.hasAlphaChannel()
    assert image.width() % 3 == 0
    assert image.height() % 2 == 0
    assert image.pixelColor(0, 0).alpha() == 0


def test_idle_blink_frame_renders_without_paint_error(app, tmp_path: Path) -> None:
    window = make_window(tmp_path)
    window.pet._frame = 7
    image = window.pet.grab().toImage()
    assert not image.isNull()
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
    assert window.pet.activity is PetActivity.CRITICAL
    assert "见底" in window.bubble.status.text()
    assert "5%" in window.bubble.five_hour.detail.text()
    window.deleteLater()


def test_usage_visibility_is_saved(app, tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    window = PetWindow(AppSettings(), SettingsStore(path), StartupManager(registry=None))
    window.set_usage_visible(False)
    assert not window.bubble.isVisible()
    assert SettingsStore(path).load().show_usage is False
    window.deleteLater()


@pytest.mark.parametrize(
    ("used", "expected_state", "expected_activity"),
    [
        (20, PetState.NORMAL, PetActivity.IDLE),
        (75, PetState.LOW, PetActivity.SIT),
        (95, PetState.CRITICAL, PetActivity.CRITICAL),
        (100, PetState.EMPTY, PetActivity.SLEEP),
    ],
)
def test_quota_states_drive_expected_pet_pose(
    app, tmp_path: Path, used: int, expected_state: PetState, expected_activity: PetActivity
) -> None:
    window = make_window(tmp_path)
    window.set_snapshot(
        parse_rate_limits(
            {"rateLimits": {"primary": {"usedPercent": used, "windowDurationMins": 300}}}
        )
    )
    assert window.pet.state is expected_state
    assert window.pet.activity is expected_activity
    window.deleteLater()


def test_recovered_stretches_then_returns_to_normal(app, tmp_path: Path) -> None:
    window = make_window(tmp_path)
    low = parse_rate_limits(
        {"rateLimits": {"primary": {"usedPercent": 95, "windowDurationMins": 300}}}
    )
    recovered = parse_rate_limits(
        {"rateLimits": {"primary": {"usedPercent": 15, "windowDurationMins": 300}}}
    )
    window.set_snapshot(low)
    window.set_snapshot(recovered)
    assert window.pet.state is PetState.RECOVERED
    assert window.pet.activity is PetActivity.STRETCH
    assert "恢复" in window.bubble.status.text()
    window._finish_recovered()
    assert window.pet.state is PetState.NORMAL
    assert window.pet.activity is PetActivity.IDLE
    window.deleteLater()


def test_interaction_settings_round_trip(app, tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    window = PetWindow(AppSettings(), store, StartupManager(registry=None))
    window.move(QPoint(120, 130))
    window.set_opacity(0.8)
    window.set_usage_visible(False)
    window.set_refresh_interval(120)
    window.set_always_on_top(False)
    window.set_locked(True)
    window.save_settings()

    restored = store.load()
    assert (restored.window_x, restored.window_y) == (120, 130)
    assert restored.opacity == 0.8
    assert restored.show_usage is False
    assert restored.refresh_interval == 120
    assert restored.always_on_top is False
    assert restored.locked is True

    other = PetWindow(restored, store, StartupManager(registry=None))
    other._restore_position()
    assert other.pos() == QPoint(120, 130)
    assert other.windowOpacity() == pytest.approx(0.8)
    assert not other.bubble.isVisible()
    assert not other.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    window.deleteLater()
    other.deleteLater()


def test_menu_tray_screen_and_dpi_basics(app, tmp_path: Path) -> None:
    window = make_window(tmp_path)
    menu = window.build_menu()
    labels = {action.text() for action in menu.actions() if action.text()}
    assert {"刷新额度", "显示额度", "始终置顶", "锁定位置", "开机启动", "退出"} <= labels
    assert app.primaryScreen() is not None
    assert app.primaryScreen().devicePixelRatio() > 0
    assert window._bounded_position(QPoint(-100000, -100000)).x() > -100000

    tray = TrayIcon(window.build_menu, window.toggle_visible)
    tray.refresh_menu()
    assert tray.icon.contextMenu() is not None
    assert tray._menu is tray.icon.contextMenu()
    tray.hide()
    window.deleteLater()


def test_drag_gesture_and_position_lock(app, tmp_path: Path) -> None:
    window = make_window(tmp_path)
    window.show()
    app.processEvents()
    point = QPoint(30, 30)

    QTest.mousePress(window.pet, Qt.MouseButton.LeftButton, pos=point)
    assert window._drag_offset is not None
    QTest.mouseRelease(window.pet, Qt.MouseButton.LeftButton, pos=point)
    assert window._drag_offset is None
    assert window._save_timer.isActive()

    window.set_locked(True)
    QTest.mousePress(window.pet, Qt.MouseButton.LeftButton, pos=point)
    assert window._drag_offset is None
    QTest.mouseRelease(window.pet, Qt.MouseButton.LeftButton, pos=point)
    window.deleteLater()


def test_pet_click_toggles_usage_panel_with_fade(app, tmp_path: Path) -> None:
    window = make_window(tmp_path)
    window.show()
    app.processEvents()
    point = QPoint(100, 100)

    QTest.mouseClick(window.pet, Qt.MouseButton.LeftButton, pos=point)
    QTest.qWait(240)
    assert window.settings.show_usage is False
    assert window.bubble.isHidden()

    QTest.mouseClick(window.pet, Qt.MouseButton.LeftButton, pos=point)
    QTest.qWait(240)
    assert window.settings.show_usage is True
    assert window.bubble.isVisible()
    assert window.bubble._opacity_effect.opacity() == pytest.approx(1.0)
    window.deleteLater()

