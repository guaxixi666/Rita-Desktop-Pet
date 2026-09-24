from __future__ import annotations

import logging
import threading
import time
import traceback

from PySide6.QtCore import QObject, Signal

from codex_usage_pet.codex.app_server_client import AppServerError, CodexAppServerClient
from codex_usage_pet.codex.rate_limits import parse_account, parse_rate_limits
from codex_usage_pet.services.logger import redact

LOGGER = logging.getLogger(__name__)


class UsageService(QObject):
    usage_updated = Signal(object)
    read_failed = Signal(str)
    connection_changed = Signal(bool)

    def __init__(
        self,
        refresh_interval: int = 60,
        *,
        client: CodexAppServerClient | None = None,
    ) -> None:
        super().__init__()
        self._interval = max(30, refresh_interval)
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._client = client or CodexAppServerClient(
            notification_handler=self._notification
        )

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="usage-refresh", daemon=True)
        self._thread.start()

    def refresh_now(self) -> None:
        self._wake.set()

    def set_interval(self, seconds: int) -> None:
        self._interval = max(30, min(900, int(seconds)))
        self._wake.set()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        self._client.close()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _notification(self, method: str, _params: dict) -> None:
        if method == "account/rateLimits/updated":
            LOGGER.info("Rate-limit update notification received")
            self._wake.set()

    def _run(self) -> None:
        failures = 0
        last_attempt = 0.0
        while not self._stop.is_set():
            elapsed = time.monotonic() - last_attempt
            if elapsed < 1.0 and self._stop.wait(1.0 - elapsed):
                break
            last_attempt = time.monotonic()
            try:
                account_payload = self._client.read_account()
                rate_limits_payload = self._client.read_rate_limits()
                try:
                    account = parse_account(account_payload)
                    snapshot = parse_rate_limits(rate_limits_payload, account)
                except Exception as exc:
                    raise AppServerError(
                        "Unable to parse App Server usage response",
                        stage="response_parse",
                        original=exc,
                    ) from exc
                LOGGER.info("response_parse: OK")
                failures = 0
                self.usage_updated.emit(snapshot)
                self.connection_changed.emit(True)
                LOGGER.info(
                    "Usage read succeeded: 5h=%s weekly=%s",
                    None if snapshot.five_hour is None else snapshot.five_hour.used_percent,
                    None if snapshot.weekly is None else snapshot.weekly.used_percent,
                )
                delay = self._interval
            except Exception as exc:
                if self._stop.is_set():
                    break
                failures += 1
                self.connection_changed.emit(False)
                self.read_failed.emit("暂时无法读取额度")
                safe_traceback = redact("".join(traceback.format_exception(exc)))
                LOGGER.error("Usage read failed: %s\n%s", redact(str(exc)), safe_traceback)
                delay = min(self._interval, 5 * (2 ** min(failures, 4)))
            self._wake.wait(delay)
            self._wake.clear()
