from __future__ import annotations

import threading
import time

from PySide6.QtCore import QCoreApplication

from codex_usage_pet.services.usage_service import UsageService


class RecoveringClient:
    def __init__(self) -> None:
        self.attempts = 0
        self.closed = False

    def read_account(self) -> dict:
        return {"account": {"type": "chatgpt", "planType": "plus"}}

    def read_rate_limits(self) -> dict:
        self.attempts += 1
        if self.attempts == 1:
            raise RuntimeError("temporary outage")
        return {
            "rateLimits": {
                "primary": {"usedPercent": 20, "windowDurationMins": 300},
                "secondary": {"usedPercent": 40, "windowDurationMins": 10080},
            }
        }

    def close(self) -> None:
        self.closed = True


def test_temporary_failure_emits_error_then_recovers(caplog) -> None:
    app = QCoreApplication.instance() or QCoreApplication([])
    client = RecoveringClient()
    service = UsageService(client=client)  # type: ignore[arg-type]
    failed = threading.Event()
    recovered = threading.Event()
    errors: list[str] = []

    service.read_failed.connect(lambda text: (errors.append(text), failed.set()))
    service.usage_updated.connect(lambda _snapshot: recovered.set())
    service.start()
    try:
        assert _wait_for(app, failed, 3)
        assert errors == ["暂时无法读取额度"]
        assert service._thread is not None and service._thread.is_alive()
        service.refresh_now()
        assert _wait_for(app, recovered, 3)
        assert client.attempts >= 2
    finally:
        service.stop()

    assert client.closed
    assert service._thread is not None and not service._thread.is_alive()
    assert "temporary outage" in caplog.text
    assert "Traceback" in caplog.text


def _wait_for(app: QCoreApplication, event: threading.Event, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if event.wait(0.01):
            return True
    return False
