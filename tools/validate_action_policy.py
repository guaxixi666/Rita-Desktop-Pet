"""Exercise action-policy selection through a native Qt PetWindow."""

from __future__ import annotations

import json
import random
import sys
import tempfile
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from codex_usage_pet.pet.action_policy import ActionEvent
from codex_usage_pet.services.settings import AppSettings, SettingsStore
from codex_usage_pet.services.startup import StartupManager
from codex_usage_pet.ui.pet_window import PetWindow


def main() -> int:
    app = QApplication.instance() or QApplication([])
    root = PROJECT_ROOT
    settings_path = Path(tempfile.gettempdir()) / "codex-usage-pet-policy-qa.json"
    window = PetWindow(
        AppSettings(show_usage=False),
        SettingsStore(settings_path),
        StartupManager(registry=None),
    )
    window.pet._rng = random.Random(20260924)
    window.pet.action_selector.rng = window.pet._rng
    window._move_to_anchor(QPoint(900, 700))
    window.show()
    app.processEvents()
    anchor = window.pet_anchor
    outcomes: dict[str, Counter[str]] = {}

    for event_index, (event, priority) in enumerate((
        (ActionEvent.CLICK, window.pet.PRIORITY_CLICK),
        (ActionEvent.IDLE_RANDOM, window.pet.PRIORITY_IDLE),
    )):
        counts: Counter[str] = Counter()
        for index in range(60):
            now = 10_000.0 + event_index * 100_000.0 + index * 400.0
            decision = window.pet._choose(event, window.pet.state, now=now)
            counts[decision.action or "none"] += 1
            started = window.pet._start_decision(decision, priority, now)
            if started:
                window.pet._finish_action()
            app.processEvents()
            assert window.pet_anchor == anchor
        outcomes[event.value] = counts

    for event, counts in outcomes.items():
        animated = {action for action, count in counts.items() if action != "none" and count}
        if len(animated) < 2:
            raise AssertionError(f"{event} did not produce multiple animation choices: {counts}")

    report = {
        "skin": window.current_skin.id,
        "events": [ActionEvent.CLICK.value, ActionEvent.IDLE_RANDOM.value],
        "hover_enabled": False,
        "quota_state_filtering": False,
        "iterations_per_event": 60,
        "anchor": [anchor.x(), anchor.y()],
        "anchor_preserved": window.pet_anchor == anchor,
        "outcomes": {event: dict(counts) for event, counts in outcomes.items()},
        "recent_history": list(window.pet.action_selector.history),
    }
    output = root / "artifacts" / "action-policy-validation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    window.close()
    window.deleteLater()
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
