from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from codex_usage_pet.codex.rate_limits import parse_rate_limits
from codex_usage_pet.pet.animator import PetActivity
from codex_usage_pet.pet.states import PetState
from codex_usage_pet.services.settings import AppSettings, SettingsStore
from codex_usage_pet.services.startup import StartupManager
from codex_usage_pet.skins.loader import SkinRepository
from codex_usage_pet.ui.action_settings import ActionSettingsDialog
from codex_usage_pet.ui.pet_widget import PetWidget
from codex_usage_pet.ui.pet_window import PetWindow


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _skin():
    return SkinRepository([Path(__file__).parents[1] / "skins"]).scan()["rita_umbral_rose"]


def _window(tmp_path: Path) -> PetWindow:
    return PetWindow(AppSettings(), SettingsStore(tmp_path / "settings.json"), StartupManager(registry=None))


def _snapshot(remaining: int):
    return parse_rate_limits(
        {"rateLimits": {"primary": {"usedPercent": 100 - remaining, "windowDurationMins": 300}}}
    )


def _finish(widget: PetWidget, action: str) -> None:
    for _ in range(widget.skin.asset_for(action).frame_count):
        widget._advance_frame()


@pytest.mark.parametrize("remaining", [100, 50, 10, 0])
def test_quota_change_never_changes_pet_animation(app, tmp_path: Path, remaining: int) -> None:
    window = _window(tmp_path)
    before = (window.pet.activity, window.pet.animation_busy, QPointF(window.pet.current_foot_anchor))
    window.set_snapshot(_snapshot(remaining))
    assert (window.pet.activity, window.pet.animation_busy, window.pet.current_foot_anchor) == before


@pytest.mark.parametrize("remaining", [100, 50, 10, 0])
def test_click_works_at_every_quota_level(app, tmp_path: Path, remaining: int) -> None:
    window = _window(tmp_path)
    window.set_snapshot(_snapshot(remaining))
    window.pet.set_action_overrides({"click": ["wave"]})
    assert window.pet.play_click_reaction(now=10.0)
    assert window.pet.activity is PetActivity.WAVE
    assert window.pet.animation_busy


@pytest.mark.parametrize("state", list(PetState))
def test_random_idle_works_for_every_legacy_quota_state(app, state: PetState) -> None:
    widget = PetWidget(_skin(), action_overrides={"idle_random": ["blink"]})
    widget.set_state(state)
    widget.action_selector.policy = replace(widget.action_selector.policy, idle_trigger_probability=1.0)
    widget._run_idle_action()
    assert widget.activity is PetActivity.BLINK


@pytest.mark.parametrize("action", ["sit", "sleepy"])
def test_long_one_shot_releases_busy_and_allows_next_action(app, action: str) -> None:
    widget = PetWidget(_skin(), action_overrides={"click": ["wave"]})
    assert widget.play_action(action)
    assert widget.animation_busy
    _finish(widget, action)
    assert widget.activity is PetActivity.IDLE
    assert not widget.animation_busy
    assert widget.play_click_reaction(now=10.0)
    assert widget.activity is PetActivity.WAVE


def test_action_settings_only_show_click_and_random_idle(app) -> None:
    dialog = ActionSettingsDialog(_skin(), {})
    assert [card.card_id for card in dialog._cards] == ["click", "idle_random"]


def test_action_duration_targets_and_hold_frames(app) -> None:
    skin = _skin()
    expected = {
        "blink": (500, 700),
        "smile": (1000, 1500),
        "surprised": (1000, 1600),
        "wave": (2200, 3200),
        "tidy_hair": (2500, 3500),
        "sit": (4000, 6000),
        "sleepy": (3000, 5000),
    }
    for action, bounds in expected.items():
        asset = skin.asset_for(action)
        assert bounds[0] <= asset.duration_ms <= bounds[1]
        assert asset.fps >= 20
        assert len(asset.frame_durations_ms) == asset.frame_count
    assert max(skin.asset_for("sit").frame_durations_ms) >= 1000
    assert max(skin.asset_for("sleepy").frame_durations_ms) >= 1000


@pytest.mark.parametrize("action", ["sit", "sleepy"])
def test_real_qtimer_one_shot_returns_to_idle(app, action: str) -> None:
    widget = PetWidget(_skin())
    widget.show()
    assert widget.play_action(action)
    QTest.qWait(widget.skin.asset_for(action).duration_ms + 250)
    assert widget.activity is PetActivity.IDLE
    assert not widget.animation_busy
    widget.close()
