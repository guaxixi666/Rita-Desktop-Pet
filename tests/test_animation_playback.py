from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint
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
    assert (asset.frame_count, asset.fps, asset.loop) == (6, 14.0, False)
    assert widget._start_action(PetActivity.BLINK)
    visited = []
    for _ in range(asset.frame_count - 1):
        visited.append(widget._frame_index)
        widget._advance_frame()
    assert visited == [0, 1, 2, 3, 4]
    widget._advance_frame()
    assert widget.activity is PetActivity.IDLE


def test_click_animation_returns_to_low_sit(app) -> None:
    widget = PetWidget(_packs()["rita_umbral_rose"])
    widget.set_state(PetState.LOW)
    assert widget.play_click_reaction(now=10.0)
    _finish_frames(widget, PetActivity.CLICK)
    assert widget.activity is PetActivity.SIT


def test_sleep_react_returns_to_sleep(app) -> None:
    widget = PetWidget(_packs()["rita_umbral_rose"])
    widget.set_state(PetState.EMPTY)
    assert widget.play_click_reaction(now=10.0)
    assert widget.activity is PetActivity.SLEEP_REACT
    _finish_frames(widget, PetActivity.SLEEP_REACT)
    assert widget.activity is PetActivity.SLEEP


def test_wave_is_one_shot_not_looping(app) -> None:
    widget = PetWidget(_packs()["rita_umbral_rose"])
    asset = widget.skin.asset_for(PetActivity.WAVE)
    assert asset.loop is False
    assert widget._start_action(PetActivity.WAVE)
    _finish_frames(widget, PetActivity.WAVE)
    assert widget.activity is PetActivity.IDLE
    assert not widget._frame_timer.isActive()


@pytest.mark.parametrize("state", [PetState.LOW, PetState.CRITICAL, PetState.EMPTY])
def test_random_animation_never_overrides_quota_state(app, state: PetState) -> None:
    widget = PetWidget(_packs()["rita_umbral_rose"])
    widget.set_state(state)
    expected = widget.activity
    widget._run_idle_action()
    assert widget.activity is expected
    assert widget._action_activity is None


def test_recovered_animation_returns_to_normal_after_declared_duration(app, tmp_path: Path) -> None:
    window = _window(tmp_path)
    window.set_snapshot(
        parse_rate_limits({"rateLimits": {"primary": {"usedPercent": 95}}})
    )
    window.set_snapshot(
        parse_rate_limits({"rateLimits": {"primary": {"usedPercent": 15}}})
    )
    assert window.pet.activity is PetActivity.STRETCH
    QTest.qWait(window.pet.current_animation_duration_ms + 180)
    assert window.pet.state is PetState.NORMAL
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
    ],
)
def test_every_animation_frame_keeps_screen_anchor(app, tmp_path: Path, activity: PetActivity) -> None:
    window = _window(tmp_path)
    if activity is PetActivity.SLEEP_REACT:
        window.pet.set_state(PetState.EMPTY)
    before = window.pet_anchor
    assert window.pet._start_action(activity)
    asset = window.pet.skin.asset_for(activity)
    for _ in range(asset.frame_count):
        assert window.pet_anchor == before
        window.pet._advance_frame()
    assert window.pet_anchor == before


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
    before = (window.geometry(), window.pet_anchor)
    assert window.pet.play_click_reaction(now=10.0)
    _finish_frames(window.pet, PetActivity.CLICK)
    assert (window.geometry(), window.pet_anchor) == before


def test_click_animation_keeps_bubble_position(app, tmp_path: Path) -> None:
    window = _window(tmp_path)
    before = window.bubble.pos()
    assert window.pet.play_click_reaction(now=10.0)
    for _ in range(window.pet.skin.asset_for(PetActivity.CLICK).frame_count):
        assert window.bubble.pos() == before
        window.pet._advance_frame()
    assert window.bubble.pos() == before


def test_continuous_hover_does_not_restart_sequence(app) -> None:
    widget = PetWidget(_packs()["rita_umbral_rose"])
    assert widget.play_hover_reaction(now=10.0)
    widget._advance_frame()
    frame = widget._frame_index
    assert not widget.play_hover_reaction(now=10.2)
    assert widget._frame_index == frame
