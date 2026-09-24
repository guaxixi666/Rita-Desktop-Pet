from __future__ import annotations

import hashlib
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from codex_usage_pet.pet.action_policy import ActionEvent, NONE_ACTION
from codex_usage_pet.pet.animator import PetActivity
from codex_usage_pet.app import build_parser
from codex_usage_pet.services.settings import AppSettings, SettingsStore
from codex_usage_pet.services.startup import StartupManager
from codex_usage_pet.skins.loader import SkinRepository
from codex_usage_pet.ui.action_settings import ActionChip
from codex_usage_pet.ui.pet_widget import PetWidget
from codex_usage_pet.ui.pet_window import PetWindow


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _skin(skin_id: str = "rita_moonlit_rose"):
    return SkinRepository([Path(__file__).parents[1] / "skins"]).scan()[skin_id]


def _hash(image: QImage) -> str:
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    return hashlib.sha256(bytes(rgba.constBits())).hexdigest()


@pytest.mark.parametrize(
    ("activity", "expected_frames"),
    [(PetActivity.BLINK, 6), (PetActivity.HOVER, 6), (PetActivity.CLICK, 8), (PetActivity.WAVE, 8)],
)
def test_normalized_animation_frames_have_unique_pixels_and_one_canvas(
    app, activity: PetActivity, expected_frames: int
) -> None:
    widget = PetWidget(_skin())
    widget.show()
    asset = widget.skin.asset_for(activity)
    hashes: list[str] = []
    sizes = set()
    anchors = set()
    for index in range(asset.frame_count):
        widget.activity = activity
        widget._frame_index = index
        widget._prepare_visual()
        app.processEvents()
        hashes.append(_hash(widget.grab().toImage()))
        sizes.add((widget.width(), widget.height()))
        anchors.add((widget.current_foot_anchor.x(), widget.current_foot_anchor.y()))
    assert asset.frame_count == expected_frames
    assert len(set(hashes)) == expected_frames
    assert len(sizes) == 1
    assert len(anchors) == 1


def test_real_qtimer_advances_frame_and_restores_idle(app) -> None:
    widget = PetWidget(_skin())
    assert widget.play_action("blink")
    assert widget._frame_timer.isActive()
    assert widget._frame_timer.interval() == 150
    QTest.qWait(190)
    assert widget._frame_index >= 1
    QTest.qWait(widget.current_animation_duration_ms + 120)
    assert widget.activity is PetActivity.IDLE
    assert widget._frame_index == 0


def test_cache_identity_includes_asset_cell_and_grid(app) -> None:
    widget = PetWidget(_skin())
    asset = widget.skin.asset_for(PetActivity.BLINK)
    first = widget._frame_pixmap(asset, asset.cell_at(0))
    again = widget._frame_pixmap(asset, asset.cell_at(0))
    second = widget._frame_pixmap(asset, asset.cell_at(1))
    assert first.cacheKey() == again.cacheKey()
    assert first.cacheKey() != second.cacheKey()
    assert (asset.path, asset.cell_at(0), asset.grid) in widget._frame_cache
    assert (asset.path, asset.cell_at(1), asset.grid) in widget._frame_cache


def test_chinese_action_chip_preserves_english_action_id(app) -> None:
    chip = ActionChip("blink")
    assert chip.text() == "眨眼"
    assert chip.action_id == "blink"
    assert chip.property("action_id") == "blink"


def test_quiet_mode_does_not_block_direct_animation_test(app) -> None:
    widget = PetWidget(_skin())
    widget.set_quiet_mode(True)
    assert not widget.play_hover_reaction(now=10.0)
    assert widget.play_action("wave")
    assert widget.activity is PetActivity.WAVE
    assert widget._frame_timer.isActive()


@pytest.mark.parametrize("skin_id", ["rita_umbral_rose", "rita_moonlit_rose"])
def test_default_hover_and_click_pools_always_offer_visible_actions(app, skin_id: str) -> None:
    skin = _skin(skin_id)
    for event in (ActionEvent.HOVER, ActionEvent.CLICK):
        assert all(candidate.action != NONE_ACTION for candidate in skin.action_policy.pool(event))


def test_real_pet_click_event_starts_animation_without_geometry_drift(app, tmp_path: Path) -> None:
    window = PetWindow(
        AppSettings(show_usage=False),
        SettingsStore(tmp_path / "settings.json"),
        StartupManager(registry=None),
    )
    window.pet.set_action_overrides({"click": ["click"]})
    window.show()
    app.processEvents()
    before = (window.pos(), window.size(), window.pet.current_foot_anchor)
    QTest.mouseClick(
        window.pet,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(window.pet.width() // 2, window.pet.height() // 2),
    )
    assert window.pet.activity is PetActivity.CLICK
    assert window.pet._frame_timer.isActive()
    QTest.qWait(190)
    assert window.pet._frame_index >= 1
    assert (window.pos(), window.size(), window.pet.current_foot_anchor) == before


def test_skin_switch_keeps_direct_animation_playable(app) -> None:
    packs = SkinRepository([Path(__file__).parents[1] / "skins"]).scan()
    widget = PetWidget(packs["rita_umbral_rose"])
    widget.apply_skin(packs["rita_moonlit_rose"])
    assert widget.play_action("click")
    assert widget._frame_timer.isActive()
    assert widget._frame_index == 0


def test_hidden_animation_test_cli_preserves_english_action_id() -> None:
    args = build_parser().parse_args(["--animation-test", "wave"])
    assert args.animation_test == "wave"
