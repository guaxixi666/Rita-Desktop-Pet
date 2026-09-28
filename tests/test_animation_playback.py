from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, QPointF
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from codex_usage_pet.codex.rate_limits import parse_rate_limits
from codex_usage_pet.pet.animator import PetActivity
from codex_usage_pet.pet.states import PetState
from codex_usage_pet.services.settings import AppSettings, SettingsStore
from codex_usage_pet.services.startup import StartupManager
from codex_usage_pet.skins.loader import SkinRepository, load_skin
from codex_usage_pet.ui.pet_widget import PetWidget
from codex_usage_pet.ui.pet_window import PetWindow


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _packs():
    root = Path(__file__).parents[1] / "skins"
    repository = SkinRepository([root])
    return repository.scan()


def _window(tmp_path: Path) -> PetWindow:
    window = PetWindow(
        AppSettings(),
        SettingsStore(tmp_path / "settings.json"),
        StartupManager(registry=None),
    )
    window._move_to_anchor(QPoint(500, 500))
    return window


def _finish_frames(widget: PetWidget, activity: PetActivity) -> None:
    for _ in range(widget.skin.asset_for(activity).frame_count):
        widget._advance_frame()


def test_blink_frame_sequence_is_declared_and_returns_idle(app) -> None:
    widget = PetWidget(_packs()["rita_umbral_rose"])
    asset = widget.skin.asset_for(PetActivity.BLINK)
    assert (asset.frame_count, asset.fps, asset.loop) == (6, 20.0, False)
    assert asset.frame_durations_ms == (150, 70, 70, 110, 70, 130)
    assert asset.duration_ms == 600
    assert widget._start_action(PetActivity.BLINK)
    visited = []
    for _ in range(asset.frame_count - 1):
        visited.append(widget._frame_index)
        widget._advance_frame()
    assert visited == [0, 1, 2, 3, 4]
    widget._advance_frame()
    assert widget.activity is PetActivity.IDLE


def test_click_animation_at_low_quota_returns_to_idle(app) -> None:
    widget = PetWidget(
        _packs()["rita_umbral_rose"],
        action_overrides={"click": ["surprised"]},
    )
    widget.set_state(PetState.LOW)
    assert widget.play_click_reaction(now=10.0)
    _finish_frames(widget, PetActivity.CLICK)
    assert widget.activity is PetActivity.IDLE


def test_sleepy_action_returns_to_idle_at_empty_quota(app) -> None:
    widget = PetWidget(
        _packs()["rita_umbral_rose"],
        action_overrides={"click": ["sleepy"]},
    )
    widget.set_state(PetState.EMPTY)
    assert widget.play_click_reaction(now=10.0)
    assert widget.activity == "sleepy"
    for _ in range(widget.skin.asset_for("sleepy").frame_count):
        widget._advance_frame()
    assert widget.activity is PetActivity.IDLE


def test_wave_is_one_shot_not_looping(app) -> None:
    widget = PetWidget(_packs()["rita_umbral_rose"])
    asset = widget.skin.asset_for(PetActivity.WAVE)
    assert asset.loop is False
    assert widget._start_action(PetActivity.WAVE)
    _finish_frames(widget, PetActivity.WAVE)
    assert widget.activity is PetActivity.IDLE
    assert not widget._frame_timer.isActive()


@pytest.mark.parametrize("state", list(PetState))
def test_random_animation_runs_in_every_quota_state(app, state: PetState) -> None:
    widget = PetWidget(
        _packs()["rita_umbral_rose"], action_overrides={"idle_random": ["blink"]}
    )
    widget.set_state(state)
    widget.action_selector.policy = replace(
        widget.action_selector.policy, idle_trigger_probability=1.0
    )
    widget._run_idle_action()
    assert widget.activity is PetActivity.BLINK


def test_recovered_quota_change_does_not_start_animation(app, tmp_path: Path) -> None:
    window = _window(tmp_path)
    window.set_snapshot(
        parse_rate_limits({"rateLimits": {"primary": {"usedPercent": 95}}})
    )
    window.set_snapshot(
        parse_rate_limits({"rateLimits": {"primary": {"usedPercent": 15}}})
    )
    assert window.pet.activity is PetActivity.IDLE


@pytest.mark.parametrize(
    "activity",
    [
        PetActivity.BLINK,
        PetActivity.HOVER,
        PetActivity.CLICK,
        PetActivity.WAVE,
        PetActivity.STRETCH,
        PetActivity.SLEEP_REACT,
        PetActivity.SIT_TRANSITION,
    ],
)
def test_every_animation_frame_keeps_screen_anchor(app, tmp_path: Path, activity: PetActivity) -> None:
    window = _window(tmp_path)
    before = window.pet_anchor
    assert window.pet._start_action(activity)
    asset = window.pet.skin.asset_for(activity)
    for _ in range(asset.frame_count):
        assert window.pet_anchor == before
        window.pet._advance_frame()
    assert window.pet_anchor == before


@pytest.mark.parametrize(
    "activity",
    [
        PetActivity.HOVER,
        PetActivity.CLICK,
        PetActivity.WAVE,
        PetActivity.SIT_TRANSITION,
        PetActivity.STRETCH,
        PetActivity.SLEEP_REACT,
    ],
)
def test_animation_playback_keeps_window_geometry_size_and_foot_anchor(
    app, tmp_path: Path, activity: PetActivity
) -> None:
    window = _window(tmp_path)
    before = (window.pos(), window.geometry(), window.size(), window.pet.size())
    foot = QPointF(window.pet.current_foot_anchor)
    assert window.pet._start_action(activity)
    asset = window.pet.skin.asset_for(activity)
    for _ in range(asset.frame_count):
        assert (window.pos(), window.geometry(), window.size(), window.pet.size()) == before
        assert window.pet.current_foot_anchor == foot
        window.pet._advance_frame()
    assert (window.pos(), window.geometry(), window.size(), window.pet.size()) == before
    assert window.pet.current_foot_anchor == foot


def test_animation_playback_never_calls_adjust_size(app, tmp_path: Path) -> None:
    window = _window(tmp_path)
    calls = 0

    def forbidden() -> None:
        nonlocal calls
        calls += 1

    window.pet.adjustSize = forbidden  # type: ignore[method-assign]
    assert window.pet._start_action(PetActivity.WAVE)
    _finish_frames(window.pet, PetActivity.WAVE)
    assert calls == 0


def test_all_animation_frames_share_one_logical_canvas(app) -> None:
    widget = PetWidget(_packs()["rita_umbral_rose"])
    initial_size = widget.size()
    initial_union = widget.skin_union_bounds
    for activity in widget.skin.states:
        asset = widget.skin.asset_for(activity)
        widget.activity = activity
        for index in range(asset.frame_count):
            widget._frame_index = index
            widget._prepare_visual()
            assert widget.size() == initial_size
            assert widget.skin_union_bounds == initial_union


def test_normalized_frame_foot_anchor_drift_is_zero(app) -> None:
    widget = PetWidget(_packs()["rita_umbral_rose"])
    expected = QPointF(widget.current_foot_anchor)
    for activity in widget.skin.states:
        asset = widget.skin.asset_for(activity)
        widget.activity = activity
        for index in range(asset.frame_count):
            widget._frame_index = index
            widget._prepare_visual()
            key = (asset.path, asset.cell_at(index), asset.grid)
            raw_anchor = widget._frame_anchors[key]
            scale_x = widget.skin.preferred_width / widget._current_frame_pixmap.width()
            scale_y = widget.skin.preferred_height / widget._current_frame_pixmap.height()
            rendered = QPointF(
                widget._target.left() + raw_anchor.x() * scale_x,
                widget._target.top() + raw_anchor.y() * scale_y,
            )
            assert rendered.x() == pytest.approx(expected.x(), abs=0.001)
            assert rendered.y() == pytest.approx(expected.y(), abs=0.001)


def test_missing_animation_uses_static_fallback(app, tmp_path: Path) -> None:
    root = tmp_path / "minimal"
    root.mkdir()
    source = Path(__file__).parents[1] / "skins" / "rita_umbral_rose" / "rita_sprite_sheet.png"
    (root / "sheet.png").write_bytes(source.read_bytes())
    (root / "skin.json").write_text(
        json.dumps({"id": "minimal", "name": "Minimal", "states": {"idle": "sheet.png"}}),
        encoding="utf-8",
    )
    widget = PetWidget(load_skin(root / "skin.json"))
    assert not widget.skin.has_explicit_state(PetActivity.WAVE)
    assert widget.skin.asset_for(PetActivity.WAVE).fallback_from is PetActivity.IDLE
    assert not widget.play_hover_reaction(now=10.0)
    assert widget.activity is PetActivity.IDLE


def test_frame_cache_reuses_decoded_frames(app) -> None:
    widget = PetWidget(_packs()["rita_umbral_rose"])
    assert widget._start_action(PetActivity.BLINK)
    for _ in range(5):
        widget._advance_frame()
    cached = widget.frame_cache_size
    widget._finish_action()
    widget._start_action(PetActivity.BLINK)
    for _ in range(5):
        widget._advance_frame()
    assert widget.frame_cache_size == cached


def test_skin_change_releases_old_frame_cache(app) -> None:
    packs = _packs()
    widget = PetWidget(packs["rita_umbral_rose"])
    widget._start_action(PetActivity.WAVE)
    widget._advance_frame()
    old_root = packs["rita_umbral_rose"].root
    assert any(path.is_relative_to(old_root) for path, _cell, _grid in widget._frame_cache)
    widget.apply_skin(packs["rita_moonlit_rose"])
    assert all(
        path.is_relative_to(packs["rita_moonlit_rose"].root)
        for path, _cell, _grid in widget._frame_cache
    )


def test_animation_end_restores_pet_geometry(app, tmp_path: Path) -> None:
    window = _window(tmp_path)
    window.pet.set_action_overrides({"click": ["surprised"]})
    before = (window.geometry(), window.pet_anchor)
    assert window.pet.play_click_reaction(now=10.0)
    _finish_frames(window.pet, PetActivity.CLICK)
    assert (window.geometry(), window.pet_anchor) == before


def test_click_animation_keeps_bubble_position(app, tmp_path: Path) -> None:
    window = _window(tmp_path)
    window.pet.set_action_overrides({"click": ["surprised"]})
    before = window.bubble.pos()
    assert window.pet.play_click_reaction(now=10.0)
    for _ in range(window.pet.skin.asset_for(PetActivity.CLICK).frame_count):
        assert window.bubble.pos() == before
        window.pet._advance_frame()
    assert window.bubble.pos() == before


def test_hover_interaction_is_disabled(app) -> None:
    widget = PetWidget(_packs()["rita_umbral_rose"])
    assert not widget.play_hover_reaction(now=10.0)
    assert widget.activity is PetActivity.IDLE


def test_frame_durations_override_fps_and_preserve_hold_frames(app) -> None:
    widget = PetWidget(_packs()["rita_umbral_rose"])
    asset = widget.skin.asset_for(PetActivity.STRETCH)
    assert asset.fps == 24.0
    assert asset.duration_ms == sum(asset.frame_durations_ms) == 2920
    assert max(asset.frame_durations_ms) == 420
    assert asset.frame_duration_ms(6) == 420
    assert asset.frame_duration_ms(0) != round(1000 / asset.fps)
    assert widget._start_action(PetActivity.STRETCH)
    assert widget._frame_timer.interval() == asset.frame_durations_ms[0]
    widget._advance_frame()
    assert widget._frame_timer.interval() == asset.frame_durations_ms[1]


def test_sit_is_one_shot_and_finishes_in_idle(app) -> None:
    widget = PetWidget(_packs()["rita_umbral_rose"])
    assert widget.play_action("sit")
    for _ in range(widget.skin.asset_for("sit").frame_count):
        widget._advance_frame()
    assert widget.activity is PetActivity.IDLE
    assert widget._action_activity is None


def test_animation_totals_are_in_intended_ranges(app) -> None:
    skin = _packs()["rita_umbral_rose"]
    expected = {
        PetActivity.BLINK: (500, 700),
        PetActivity.HOVER: (900, 1300),
        PetActivity.CLICK: (1200, 1800),
        PetActivity.WAVE: (2000, 2800),
        PetActivity.STRETCH: (2500, 4000),
        PetActivity.SLEEP_REACT: (2000, 3000),
        PetActivity.SIT_TRANSITION: (1200, 1800),
        "smile": (1000, 1500),
        "surprised": (1000, 1600),
        "tidy_hair": (2500, 3500),
        "sit": (4000, 6000),
        "sleepy": (3000, 5000),
    }
    for activity, bounds in expected.items():
        assert bounds[0] <= skin.asset_for(activity).duration_ms <= bounds[1]
