from __future__ import annotations

import json
import logging
import os
import queue
import shutil
import subprocess
import threading
import time
from collections.abc import Callable, Sequence
from typing import Any

LOGGER = logging.getLogger(__name__)


class AppServerError(RuntimeError):
    pass


class AppServerRpcError(AppServerError):
    def __init__(self, code: int | None, message: str):
        super().__init__(message)
        self.code = code


NotificationHandler = Callable[[str, dict[str, Any]], None]


class CodexAppServerClient:
    """Persistent JSONL client for the official local `codex app-server`."""

    def __init__(
        self,
        command: Sequence[str] | None = None,
        *,
        timeout: float = 10.0,
        notification_handler: NotificationHandler | None = None,
    ) -> None:
        # Resolve the CLI lazily.  A missing/temporarily unavailable Codex CLI
        # must be reported by the refresh worker, not crash the desktop UI
        # while its objects are still being constructed.
        self.command = list(command) if command else None
        self.timeout = timeout
        self.notification_handler = notification_handler
        self._process: subprocess.Popen[str] | None = None
        self._next_id = 1
        self._pending: dict[int, queue.Queue[dict[str, Any]]] = {}
        self._pending_lock = threading.Lock()
        self._start_lock = threading.RLock()
        self._write_lock = threading.Lock()
        self._stopping = threading.Event()
        self._closed = threading.Event()

    @staticmethod
    def _default_command() -> list[str]:
        executable = shutil.which("codex") or shutil.which("codex.exe")
        if not executable:
            raise AppServerError("找不到 codex 命令，请先安装并登录 Codex CLI")
        return [executable, "app-server", "--listen", "stdio://"]

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process and self._process.poll() is None else None

    def start(self) -> None:
        with self._start_lock:
            if self._closed.is_set():
                raise AppServerError("Codex App Server client is closed")
            if self._process and self._process.poll() is None:
                return
            self._stopping.clear()
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            command = self.command or self._default_command()
            try:
                self._process = subprocess.Popen(
                    command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    creationflags=flags,
                )
            except OSError as exc:
                raise AppServerError(f"无法启动 Codex App Server: {exc}") from exc
            threading.Thread(target=self._read_stdout, name="codex-app-server", daemon=True).start()
            threading.Thread(target=self._drain_stderr, name="codex-app-server-stderr", daemon=True).start()
            LOGGER.info("Codex App Server started (pid=%s)", self._process.pid)
            try:
                self._round_trip(
                    "initialize",
                    {
                        "clientInfo": {
                            "name": "codex_usage_pet",
                            "title": "Codex Usage Pet",
                            "version": "0.1.0",
                        }
                    },
                )
                self._send({"method": "initialized", "params": {}})
            except Exception:
                self._close_process()
                raise

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(2):
            if self._closed.is_set():
                raise AppServerError("Codex App Server client is closed")
            try:
                self.start()
                return self._round_trip(method, params)
            except AppServerRpcError:
                raise
            except (AppServerError, OSError) as exc:
                last_error = exc
                self._close_process()
                if attempt == 0 and not self._closed.is_set():
                    time.sleep(0.25)
        raise AppServerError(str(last_error or "Codex App Server request failed"))

    def read_account(self) -> dict[str, Any]:
        return self.request("account/read", {"refreshToken": False})

    def read_rate_limits(self) -> dict[str, Any]:
        return self.request("account/rateLimits/read")

    def close(self) -> None:
        self._closed.set()
        self._close_process()

    def _close_process(self) -> None:
        with self._start_lock:
            process = self._process
            self._process = None
            self._stopping.set()
            self._fail_pending("Codex App Server stopped")
            if process is None:
                return
            if process.stdin:
                try:
                    process.stdin.close()
                except OSError:
                    pass
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=1.5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1.0)
            LOGGER.info("Codex App Server stopped")

    def __enter__(self) -> "CodexAppServerClient":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _round_trip(self, method: str, params: dict[str, Any] | None) -> dict[str, Any]:
        with self._pending_lock:
            request_id = self._next_id
            self._next_id += 1
            response_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=1)
            self._pending[request_id] = response_queue
        message: dict[str, Any] = {"id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        try:
            self._send(message)
            response = response_queue.get(timeout=self.timeout)
        except queue.Empty as exc:
            raise AppServerError(f"Codex App Server 请求超时: {method}") from exc
        finally:
            with self._pending_lock:
                self._pending.pop(request_id, None)
        if "_transport_error" in response:
            raise AppServerError(str(response["_transport_error"]))
        if "error" in response:
            error = response.get("error") or {}
            raise AppServerRpcError(error.get("code"), error.get("message") or "JSON-RPC error")
        result = response.get("result")
        return result if isinstance(result, dict) else {}

    def _send(self, message: dict[str, Any]) -> None:
        process = self._process
        if not process or process.poll() is not None or not process.stdin:
            raise AppServerError("Codex App Server 未运行")
        encoded = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        with self._write_lock:
            try:
                process.stdin.write(encoded + "\n")
                process.stdin.flush()
            except OSError as exc:
                raise AppServerError("无法写入 Codex App Server") from exc

    def _read_stdout(self) -> None:
        process = self._process
        if not process or not process.stdout:
            return
        try:
            for line in process.stdout:
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    LOGGER.warning("Ignored malformed App Server output")
                    continue
                request_id = message.get("id")
                if isinstance(request_id, int):
                    with self._pending_lock:
                        response_queue = self._pending.get(request_id)
                    if response_queue:
                        response_queue.put(message)
                    continue
                method = message.get("method")
                params = message.get("params")
                if isinstance(method, str) and self.notification_handler:
                    try:
                        self.notification_handler(method, params if isinstance(params, dict) else {})
                    except Exception:
                        LOGGER.exception("Notification handler failed for %s", method)
        finally:
            if not self._stopping.is_set():
                LOGGER.warning("Codex App Server disconnected")
                self._fail_pending("Codex App Server disconnected")

    def _drain_stderr(self) -> None:
        process = self._process
        if not process or not process.stderr:
            return
        for _line in process.stderr:
            # Deliberately discard raw stderr so credentials can never enter logs.
            LOGGER.debug("Codex App Server emitted a diagnostic line")

    def _fail_pending(self, message: str) -> None:
        with self._pending_lock:
            queues = list(self._pending.values())
        for response_queue in queues:
            try:
                response_queue.put_nowait({"_transport_error": message})
            except queue.Full:
                pass
