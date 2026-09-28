from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from codex_usage_pet.pet.animator import PetActivity
from codex_usage_pet.pet.states import PetState
from codex_usage_pet.services.settings import AppSettings, SettingsStore
from codex_usage_pet.services.startup import StartupManager
from codex_usage_pet.skins.loader import load_skin
from codex_usage_pet.ui.pet_widget import PetWidget, alpha_bounding_rect
from codex_usage_pet.ui.pet_window import PetWindow


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _window(tmp_path: Path, *, show_usage: bool = True) -> PetWindow:
    window = PetWindow(
        AppSettings(show_usage=show_usage),
        SettingsStore(tmp_path / "settings.json"),
        StartupManager(registry=None),
    )
    window._move_to_anchor(QPoint(500, 500))
    return window


def _minimal_skin(tmp_path: Path):
    root = tmp_path / "minimal"
    root.mkdir()
    source = Path(__file__).parents[1] / "skins" / "rita_umbral_rose" / "rita_sprite_sheet.png"
    target = root / "sheet.png"
    target.write_bytes(source.read_bytes())
    manifest = {
        "id": "minimal",
        "name": "Minimal",
        "states": {"idle": {"file": "sheet.png", "grid": [3, 2], "cell": [0, 0]}},
    }
    (root / "skin.json").write_text(json.dumps(manifest), encoding="utf-8")
    return load_skin(root / "skin.json")


def test_idle_does_not_move_screen_position(app, tmp_path: Path) -> None:
    window = _window(tmp_path)
    before = (window.pet_anchor, window.pos(), window.size())
    for _ in range(30):
        window.pet._advance()
    assert (window.pet_anchor, window.pos(), window.size()) == before
    window.deleteLater()


def test_hover_is_disabled_and_preserves_anchor(app, tmp_path: Path) -> None:
    window = _window(tmp_path)
    before = window.pet_anchor
    assert not window.pet.play_hover_reaction(now=10.0)
    assert window.pet_anchor == before
    window.deleteLater()


def test_click_action_preserves_anchor(app, tmp_path: Path) -> None:
    window = _window(tmp_path)
    window.pet.set_action_overrides({"click": ["surprised"]})
    before = window.pet_anchor
    assert window.pet.play_click_reaction(now=10.0)
    assert window.pet_anchor == before
    window.pet._finish_action()
    assert window.pet_anchor == before
    window.deleteLater()


def test_show_usage_does_not_change_pet_geometry(app, tmp_path: Path) -> None:
    window = _window(tmp_path, show_usage=False)
    before = (window.geometry(), window.pet_anchor)
    window.set_usage_visible(True)
    assert (window.geometry(), window.pet_anchor) == before
    window.deleteLater()


def test_hide_usage_does_not_change_pet_geometry(app, tmp_path: Path) -> None:
    window = _window(tmp_path, show_usage=True)
    before = (window.geometry(), window.pet_anchor)
    window.set_usage_visible(False)
    assert (window.geometry(), window.pet_anchor) == before
    window.deleteLater()


def test_repeated_usage_toggles_never_drift_pet(app, tmp_path: Path) -> None:
    window = _window(tmp_path, show_usage=False)
    before = (window.geometry(), window.pet_anchor)
    for _ in range(10):
        window.set_usage_visible(True)
        assert (window.geometry(), window.pet_anchor) == before
        window.set_usage_visible(False)
        assert (window.geometry(), window.pet_anchor) == before
    window.deleteLater()


def test_bubble_follows_pet_motion(app, tmp_path: Path) -> None:
    window = _window(tmp_path)
    window._position_bubble()
    relation = window.bubble.pos() - window.pet_anchor
    window._move_to_anchor(window.pet_anchor + QPoint(20, 15))
    assert window.bubble.pos() - window.pet_anchor == relation
    window.deleteLater()


def test_bubble_direction_never_moves_pet(app, tmp_path: Path) -> None:
    window = _window(tmp_path)
    area = app.primaryScreen().availableGeometry()
    window._move_to_anchor(QPoint(area.left() + 70, area.center().y()))
    left_anchor = window.pet_anchor
    assert window.bubble_side == "right"
    assert window.pet_anchor == left_anchor
    window._move_to_anchor(QPoint(area.right() - 70, area.center().y()))
    right_anchor = window.pet_anchor
    assert window.bubble_side == "left"
    assert window.pet_anchor == right_anchor
    window.deleteLater()


def test_alpha_bounding_rect_uses_threshold() -> None:
    image = QImage(20, 18, QImage.Format.Format_RGBA8888)
    image.fill(QColor(0, 0, 0, 0))
    for y in range(5, 13):
        for x in range(4, 15):
            image.setPixelColor(x, y, QColor(255, 255, 255, 20))
    image.setPixelColor(1, 1, QColor(255, 255, 255, 10))
    assert alpha_bounding_rect(image, 15) == QRect(4, 5, 11, 8)


def test_skin_union_bounds_stays_inside_logical_canvas(app, tmp_path: Path) -> None:
    window = _window(tmp_path)
    assert window.width() <= 232 + window.pet.SAFE_PADDING * 2
    assert window.height() <= 244 + window.pet.SAFE_PADDING * 2
    assert not window.pet.skin_union_bounds.isNull()
    window.deleteLater()


def test_missing_hover_animation_stays_idle(app, tmp_path: Path) -> None:
    widget = PetWidget(_minimal_skin(tmp_path))
    assert not widget.skin.has_explicit_state(PetActivity.HOVER)
    assert not widget.play_hover_reaction(now=10.0)
    assert widget.activity is PetActivity.IDLE
    widget.deleteLater()


def test_missing_click_animation_only_skips_reaction(app, tmp_path: Path) -> None:
    widget = PetWidget(_minimal_skin(tmp_path))
    assert not widget.skin.has_explicit_state(PetActivity.CLICK)
    assert not widget.play_click_reaction(now=10.0)
    assert widget.activity is PetActivity.IDLE
    widget.deleteLater()


@pytest.mark.parametrize("state", list(PetState))
def test_quota_states_do_not_lock_random_idle(app, tmp_path: Path, state: PetState) -> None:
    window = _window(tmp_path)
    window.pet.set_state(state)
    window.pet.set_action_overrides({"idle_random": ["blink"]})
    window.pet.action_selector.policy = replace(
        window.pet.action_selector.policy, idle_trigger_probability=1.0
    )
    window.pet._run_idle_action()
    assert window.pet.activity is PetActivity.BLINK
    assert window.pet._action_activity is PetActivity.BLINK
    window.deleteLater()


def test_empty_quota_stays_idle_until_normal_random_action(app, tmp_path: Path) -> None:
    window = _window(tmp_path)
    window.pet.set_state(PetState.EMPTY)
    assert window.pet.activity is PetActivity.IDLE
    window.deleteLater()


def test_random_idle_timer_interval_is_in_requested_range(app, tmp_path: Path) -> None:
    window = _window(tmp_path)
    for _ in range(20):
        window.pet._schedule_idle_action()
        assert 45_000 <= window.pet.idle_timer_interval <= 150_000
    window.deleteLater()


def test_click_cooldown_blocks_repeated_action(app, tmp_path: Path) -> None:
    window = _window(tmp_path)
    window.pet.set_action_overrides({"click": ["surprised"]})
    assert window.pet.play_click_reaction(now=10.0)
    window.pet._finish_action()
    assert not window.pet.play_click_reaction(now=10.5)
    assert window.pet.play_click_reaction(now=13.0)
    window.deleteLater()


def test_sit_finishes_then_click_starts_immediately(app, tmp_path: Path) -> None:
    window = _window(tmp_path)
    window.pet.set_action_overrides({"click": ["wave"]})
    assert window.pet.play_action("sit")
    for _ in range(window.pet.skin.asset_for("sit").frame_count):
        window.pet._advance_frame()
    assert window.pet.activity is PetActivity.IDLE
    assert window.pet._action_activity is None
    assert window.pet.play_click_reaction(now=10.1)
    assert window.pet.activity is PetActivity.WAVE
    window.deleteLater()


def test_hover_remains_disabled_after_pointer_reentry(app, tmp_path: Path) -> None:
    window = _window(tmp_path)
    assert not window.pet.play_hover_reaction(now=10.1)
    assert not window.pet.play_hover_reaction(now=10.5)
    window.deleteLater()
