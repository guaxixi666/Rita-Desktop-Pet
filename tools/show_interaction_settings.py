"""Open the native interaction-settings dialog for Windows screenshot QA."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication

from codex_usage_pet.skins.loader import SkinRepository
from codex_usage_pet.ui.action_settings import ActionSettingsDialog


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=30)
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    skin = SkinRepository([ROOT / "skins"]).scan()["rita_umbral_rose"]
    dialog = ActionSettingsDialog(skin, {"hover": ["blink", "hover"]})
    dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    QTimer.singleShot(max(1, args.seconds) * 1000, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
