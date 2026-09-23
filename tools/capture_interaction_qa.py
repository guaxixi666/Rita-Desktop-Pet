"""Capture native Qt interaction states for release visual QA."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QTimer
from PySide6.QtWidgets import QApplication

from codex_usage_pet.codex.models import UsageSnapshot, UsageWindow
from codex_usage_pet.pet.states import PetState
from codex_usage_pet.services.settings import AppSettings, SettingsStore
from codex_usage_pet.services.startup import StartupManager
from codex_usage_pet.ui.pet_window import PetWindow


def main() -> int:
    app = QApplication.instance() or QApplication([])
    project_root = Path(__file__).resolve().parents[1]
    output = project_root / "artifacts" / "screenshots"
    output.mkdir(parents=True, exist_ok=True)
    settings_path = Path(tempfile.gettempdir()) / "codex-usage-pet-interaction-qa.json"
    window = PetWindow(
        AppSettings(show_usage=True),
        SettingsStore(settings_path),
        StartupManager(registry=None),
    )
    now = datetime.now().astimezone()
    window.set_snapshot(
        UsageSnapshot(
            five_hour=UsageWindow(28, 300, now + timedelta(hours=2, minutes=14)),
            weekly=UsageWindow(39, 10080, now + timedelta(days=3, hours=4)),
        )
    )
    screen = app.primaryScreen()
    if screen is None:
        raise RuntimeError("No primary screen available")
    area = screen.availableGeometry()
    window._move_to_anchor(QPoint(area.center().x() + 280, area.center().y() + 190))
    window.show()
    window.bubble.show()
    before: dict[str, object] = {}

    def save_pet(name: str) -> None:
        window.grab().save(str(output / name))

    def capture_idle() -> None:
        save_pet("pet-idle.png")
        window.pet.play_hover_reaction()
        QTimer.singleShot(80, capture_hover)

    def capture_hover() -> None:
        save_pet("pet-hover.png")
        window.pet._finish_action()
        window.pet.play_click_reaction()
        QTimer.singleShot(80, capture_click)

    def capture_click() -> None:
        save_pet("pet-click.png")
        window.pet._finish_action()
        window.set_usage_visible(True)
        QTimer.singleShot(260, capture_open)

    def capture_open() -> None:
        pet_rect = window.frameGeometry()
        bubble_rect = window.bubble.frameGeometry()
        region = pet_rect.united(bubble_rect).adjusted(-16, -16, 16, 16)
        before.update(
            anchor=[window.pet_anchor.x(), window.pet_anchor.y()],
            geometry=[window.x(), window.y(), window.width(), window.height()],
            region=[region.x(), region.y(), region.width(), region.height()],
            old_area=232 * 244,
            new_area=window.width() * window.height(),
            bubble_side=window.bubble_side,
        )
        before["region_rect"] = region
        screen.grabWindow(0, region.x(), region.y(), region.width(), region.height()).save(
            str(output / "bubble-open.png")
        )
        window.pet.set_state(PetState.LOW)
        QTimer.singleShot(120, capture_sit)

    def capture_sit() -> None:
        window.pet._finish_action()
        save_pet("pet-sit.png")
        window.pet.set_state(PetState.CRITICAL)
        QTimer.singleShot(120, capture_critical)

    def capture_critical() -> None:
        save_pet("pet-critical.png")
        window.pet.set_state(PetState.EMPTY)
        QTimer.singleShot(120, capture_sleep)

    def capture_sleep() -> None:
        save_pet("pet-sleep.png")
        window.set_usage_visible(False)
        QTimer.singleShot(260, capture_closed)

    def capture_closed() -> None:
        region = before.pop("region_rect")
        assert isinstance(region, QRect)
        screen.grabWindow(0, region.x(), region.y(), region.width(), region.height()).save(
            str(output / "bubble-closed.png")
        )
        after_anchor = [window.pet_anchor.x(), window.pet_anchor.y()]
        after_geometry = [window.x(), window.y(), window.width(), window.height()]
        before["after_anchor"] = after_anchor
        before["after_geometry"] = after_geometry
        before["anchor_delta"] = [
            after_anchor[0] - before["anchor"][0],  # type: ignore[index]
            after_anchor[1] - before["anchor"][1],  # type: ignore[index]
        ]
        before["area_reduction_percent"] = round(
            (1 - before["new_area"] / before["old_area"]) * 100,  # type: ignore[operator]
            2,
        )
        print(json.dumps(before, ensure_ascii=False, indent=2))
        window.bubble.close()
        window.deleteLater()
        app.quit()

    QTimer.singleShot(600, capture_idle)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
