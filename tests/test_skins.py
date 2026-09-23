from __future__ import annotations

import json
import logging
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from codex_usage_pet.codex.rate_limits import parse_rate_limits
from codex_usage_pet.pet.animator import PetActivity
from codex_usage_pet.pet.states import PetState
from codex_usage_pet.services.settings import AppSettings, SettingsStore
from codex_usage_pet.services.startup import StartupManager
from codex_usage_pet.skins.loader import InvalidSkinError, SkinRepository, load_skin
from codex_usage_pet.skins.manager import SkinManager
from codex_usage_pet.ui.pet_window import PetWindow


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _write_skin(root: Path, skin_id: str, *, primary: str = "#123456", states=None) -> Path:
    directory = root / skin_id
    directory.mkdir(parents=True)
    (directory / "idle.png").write_bytes(b"skin-test-placeholder")
    payload = {
        "id": skin_id,
        "name": f"Skin {skin_id}",
        "author": "Tests",
        "version": "1.0",
        "preview": "idle.png",
        "preferred_width": 180,
        "preferred_height": 190,
        "anchor_x": 4,
        "anchor_y": -2,
        "theme": {"primary": primary, "decorator": "*"},
        "states": states or {"idle": "idle.png"},
    }
    (directory / "skin.json").write_text(json.dumps(payload), encoding="utf-8")
    return directory


def _manager(tmp_path: Path, settings: AppSettings, now: datetime) -> SkinManager:
    root = tmp_path / "skins"
    _write_skin(root, "skin_a", primary="#112233")
    _write_skin(root, "skin_b", primary="#445566")
    settings.current_skin = "skin_a"
    return SkinManager(
        settings,
        SettingsStore(tmp_path / "settings.json"),
        SkinRepository([root]),
        clock=lambda: now,
        rng=random.Random(7),
    )


def test_skin_scan_json_and_theme(tmp_path: Path) -> None:
    root = tmp_path / "skins"
    directory = _write_skin(root, "skin_a", primary="#ABCDEF")
    pack = load_skin(directory / "skin.json")
    repository = SkinRepository([root])
    assert list(repository.scan()) == ["skin_a"]
    assert pack.theme.primary == "#ABCDEF"
    assert pack.preferred_width == 180
    assert pack.anchor_x == 4


def test_missing_animations_fallback_without_crashing(tmp_path: Path, caplog) -> None:
    caplog.set_level(logging.INFO)
    directory = _write_skin(tmp_path, "fallback")
    pack = load_skin(directory / "skin.json")
    assert set(pack.states) == set(PetActivity)
    assert pack.asset_for(PetActivity.WALK).fallback_from is PetActivity.IDLE
    assert pack.asset_for(PetActivity.CRITICAL).fallback_from is PetActivity.SIT
    assert "Skin fallback" in caplog.text


def test_frame_durations_parse_without_fps(tmp_path: Path) -> None:
    states = {
        "idle": "idle.png",
        "blink": {
            "source": "idle.png",
            "grid": [2, 1],
            "frames": 2,
            "frame_durations_ms": [80, 220],
        },
    }
    directory = _write_skin(tmp_path, "timed", states=states)
    asset = load_skin(directory / "skin.json").asset_for(PetActivity.BLINK)
    assert asset.fps == 0
    assert asset.frame_durations_ms == (80, 220)
    assert asset.duration_ms == 300


def test_frame_duration_count_must_match_frames(tmp_path: Path) -> None:
    states = {
        "idle": "idle.png",
        "blink": {
            "source": "idle.png",
            "grid": [2, 1],
            "frames": 2,
            "frame_durations_ms": [80],
        },
    }
    directory = _write_skin(tmp_path, "bad_timing", states=states)
    with pytest.raises(InvalidSkinError, match="must match frame count"):
        load_skin(directory / "skin.json")


def test_invalid_skin_is_skipped(tmp_path: Path, caplog) -> None:
    good = _write_skin(tmp_path, "good")
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "skin.json").write_text("{broken", encoding="utf-8")
    repository = SkinRepository([tmp_path])
    assert set(repository.scan()) == {"good"}
    assert good.exists()
    assert "Invalid skin skipped" in caplog.text


def test_manual_skin_change_is_persisted(tmp_path: Path) -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    manager = _manager(tmp_path, AppSettings(), now)
    changed = manager.change("skin_b", now=now)
    restored = SettingsStore(tmp_path / "settings.json").load()
    assert changed and changed.id == "skin_b"
    assert restored.current_skin == "skin_b"
    assert restored.last_skin_change == now.isoformat()


def test_random_skin_does_not_repeat_current(tmp_path: Path) -> None:
    manager = _manager(tmp_path, AppSettings(), datetime.now(timezone.utc))
    assert manager.random_change().id == "skin_b"


def test_random_with_one_skin_is_safe(tmp_path: Path) -> None:
    root = tmp_path / "skins"
    _write_skin(root, "only")
    settings = AppSettings(current_skin="only")
    manager = SkinManager(settings, SettingsStore(tmp_path / "settings.json"), SkinRepository([root]))
    assert manager.random_change().id == "only"


def test_interval_not_due_does_not_change(tmp_path: Path) -> None:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    settings = AppSettings(
        auto_skin_enabled=True,
        auto_skin_mode="interval",
        auto_skin_interval_hours=24,
        last_skin_change=base.isoformat(),
    )
    manager = _manager(tmp_path, settings, base + timedelta(hours=23, minutes=59))
    assert manager.maybe_auto_change() is None
    assert manager.current.id == "skin_a"


def test_interval_due_changes_once_and_updates_timestamp(tmp_path: Path) -> None:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    now = base + timedelta(hours=24)
    settings = AppSettings(
        auto_skin_enabled=True,
        auto_skin_mode="interval",
        auto_skin_interval_hours=24,
        last_skin_change=base.isoformat(),
    )
    manager = _manager(tmp_path, settings, now)
    assert manager.maybe_auto_change(now).id == "skin_b"
    assert settings.last_skin_change == now.isoformat()
    assert manager.maybe_auto_change(now) is None


def test_restart_keeps_remaining_interval(tmp_path: Path) -> None:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    settings = AppSettings(
        auto_skin_enabled=True,
        auto_skin_mode="interval",
        auto_skin_interval_hours=24,
        last_skin_change=base.isoformat(),
    )
    first = _manager(tmp_path, settings, base + timedelta(hours=10))
    first.store.save(settings)
    restored = first.store.load()
    second = _manager(tmp_path / "restart", restored, base + timedelta(hours=23))
    assert second.maybe_auto_change() is None


def test_start_after_72_hours_performs_only_one_change(tmp_path: Path) -> None:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    now = base + timedelta(hours=72)
    settings = AppSettings(
        auto_skin_enabled=True,
        auto_skin_mode="interval",
        auto_skin_interval_hours=24,
        last_skin_change=base.isoformat(),
    )
    manager = _manager(tmp_path, settings, now)
    assert manager.maybe_auto_change(now) is not None
    assert manager.maybe_auto_change(now) is None


def test_clock_rollback_does_not_trigger_change(tmp_path: Path) -> None:
    last = datetime(2026, 1, 2, tzinfo=timezone.utc)
    now = last - timedelta(hours=3)
    settings = AppSettings(
        auto_skin_enabled=True,
        auto_skin_mode="interval",
        auto_skin_interval_hours=24,
        last_skin_change=last.isoformat(),
    )
    manager = _manager(tmp_path, settings, now)
    assert manager.maybe_auto_change(now) is None
    assert manager.current.id == "skin_a"


def test_fixed_local_time_changes_after_boundary(tmp_path: Path) -> None:
    local_zone = datetime.now().astimezone().tzinfo
    now_local = datetime(2026, 3, 2, 9, 0, tzinfo=local_zone)
    last_local = datetime(2026, 3, 1, 10, 0, tzinfo=local_zone)
    settings = AppSettings(
        auto_skin_enabled=True,
        auto_skin_mode="fixed_time",
        auto_skin_fixed_time="08:00",
        last_skin_change=last_local.astimezone(timezone.utc).isoformat(),
    )
    manager = _manager(tmp_path, settings, now_local.astimezone(timezone.utc))
    assert manager.maybe_auto_change() is not None


def test_fixed_local_time_waits_before_boundary(tmp_path: Path) -> None:
    local_zone = datetime.now().astimezone().tzinfo
    now_local = datetime(2026, 3, 2, 7, 0, tzinfo=local_zone)
    last_local = datetime(2026, 3, 1, 10, 0, tzinfo=local_zone)
    settings = AppSettings(
        auto_skin_enabled=True,
        auto_skin_mode="fixed_time",
        auto_skin_fixed_time="08:00",
        last_skin_change=last_local.astimezone(timezone.utc).isoformat(),
    )
    manager = _manager(tmp_path, settings, now_local.astimezone(timezone.utc))
    assert manager.maybe_auto_change() is None


def test_rescan_hot_loads_new_folder(tmp_path: Path) -> None:
    root = tmp_path / "skins"
    _write_skin(root, "first")
    settings = AppSettings(current_skin="first")
    manager = SkinManager(settings, SettingsStore(tmp_path / "settings.json"), SkinRepository([root]))
    _write_skin(root, "second")
    manager.rescan()
    assert set(manager.packs) == {"first", "second"}


@pytest.mark.parametrize(
    ("used", "expected"),
    [(20, PetState.NORMAL), (75, PetState.LOW), (95, PetState.CRITICAL), (100, PetState.EMPTY)],
)
def test_ui_skin_switch_preserves_quota_state(
    app: QApplication, tmp_path: Path, used: int, expected: PetState
) -> None:
    settings = AppSettings()
    store = SettingsStore(tmp_path / "settings.json")
    window = PetWindow(settings, store, StartupManager(registry=None))
    window.set_snapshot(
        parse_rate_limits(
            {"rateLimits": {"primary": {"usedPercent": used, "windowDurationMins": 300}}}
        )
    )
    window.change_skin("rita_moonlit_rose")
    window._skin_fade_out.stop()
    window._finish_skin_swap()
    assert window.pet.state is expected
    assert window.current_skin.id == "rita_moonlit_rose"
    assert window.bubble._theme.primary == window.current_skin.theme.primary
    window.deleteLater()


def test_skin_menu_contains_manual_random_auto_and_rescan(app: QApplication, tmp_path: Path) -> None:
    window = PetWindow(
        AppSettings(), SettingsStore(tmp_path / "settings.json"), StartupManager(registry=None)
    )
    menu = window.build_menu()
    skin_menu = next(action.menu() for action in menu.actions() if action.text() == "皮肤")
    labels = {action.text() for action in skin_menu.actions()}
    assert "Rita · Umbral Rose" in labels
    assert "Rita · Moonlit Rose" in labels
    assert {"随机换一个", "重新扫描皮肤", "打开皮肤目录"} <= labels
    assert any(action.text() == "自动换肤" for action in skin_menu.actions())
    window.deleteLater()


def test_skin_settings_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    settings = AppSettings(
        current_skin="skin_b",
        auto_skin_enabled=True,
        auto_skin_mode="fixed_time",
        auto_skin_interval_hours=48,
        auto_skin_fixed_time="18:30",
        last_skin_change="2026-01-01T00:00:00+00:00",
        random_skin_no_repeat=True,
    )
    SettingsStore(path).save(settings)
    assert SettingsStore(path).load() == settings
