"""Show one deterministic native PetWindow pose for OS-level screenshot QA."""

from __future__ import annotations

import argparse
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QPoint, QTimer
from PySide6.QtWidgets import QApplication

from codex_usage_pet.codex.models import UsageSnapshot, UsageWindow
from codex_usage_pet.pet.animator import PetActivity
from codex_usage_pet.pet.states import PetState
from codex_usage_pet.services.settings import AppSettings, SettingsStore
from codex_usage_pet.services.startup import StartupManager
from codex_usage_pet.ui.pet_window import PetWindow


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "state",
        choices=("idle", "hover", "click", "sit", "critical", "sleep", "bubble-open"),
    )
    parser.add_argument("--seconds", type=int, default=20)
    args = parser.parse_args()

    app = QApplication.instance() or QApplication([])
    store = SettingsStore(Path(tempfile.gettempdir()) / "codex-usage-pet-native-visual-qa.json")
    window = PetWindow(
        AppSettings(show_usage=args.state == "bubble-open", always_on_top=True),
        store,
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
        raise RuntimeError("No primary screen")
    area = screen.availableGeometry()
    window._move_to_anchor(QPoint(area.right() - 100, area.bottom() - 90))
    window.show()

    if args.state in {"hover", "click"}:
        activity = PetActivity.HOVER if args.state == "hover" else PetActivity.CLICK
        window.pet._frame_timer.stop()
        window.pet._action_timer.stop()
        window.pet._action_activity = activity
        window.pet.activity = activity
        window.pet._frame_index = window.pet.skin.asset_for(activity).frame_count // 2
        window.pet._prepare_visual()
        window.pet.update()
    elif args.state == "sit":
        window.pet.set_state(PetState.LOW)
        window.pet._frame_timer.stop()
        window.pet._action_activity = None
        window.pet.activity = PetActivity.SIT
        window.pet._frame_index = 0
        window.pet._prepare_visual()
        window.pet.update()
    elif args.state == "critical":
        window.pet.set_state(PetState.CRITICAL)
    elif args.state == "sleep":
        window.pet.set_state(PetState.EMPTY)

    if args.state == "bubble-open":
        window.set_usage_visible(True)
    else:
        window.set_usage_visible(False)
    QTimer.singleShot(max(1, args.seconds) * 1000, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
