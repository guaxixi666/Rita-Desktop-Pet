from __future__ import annotations

import json
import logging
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
from collections import deque
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from codex_usage_pet.services.logger import redact

LOGGER = logging.getLogger(__name__)


class AppServerError(RuntimeError):
    """App Server failure with safe, structured diagnostic context."""

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        original: BaseException | None = None,
        process_exit_code: int | None = None,
        stderr_summary: str | None = None,
        rpc_code: int | None = None,
        rpc_message: str | None = None,
    ) -> None:
        self.stage = stage
        self.original_type = type(original).__name__ if original else None
        self.original_message = redact(str(original)) if original else None
        self.process_exit_code = process_exit_code
        self.stderr_summary = redact(stderr_summary) if stderr_summary else None
        self.rpc_code = rpc_code
        self.rpc_message = redact(rpc_message) if rpc_message else None
        parts = [f"stage={stage}", redact(message)]
        if self.original_type:
            parts.append(f"cause={self.original_type}: {self.original_message}")
        if rpc_code is not None or rpc_message:
            parts.append(f"rpc={rpc_code}: {self.rpc_message or 'JSON-RPC error'}")
        if process_exit_code is not None:
            parts.append(f"exit_code={process_exit_code}")
        if self.stderr_summary:
            parts.append(f"stderr={self.stderr_summary}")
        super().__init__("; ".join(parts))


class AppServerRpcError(AppServerError):
    def __init__(
        self,
        code: int | None,
        message: str,
        *,
        stage: str,
        process_exit_code: int | None = None,
        stderr_summary: str | None = None,
    ) -> None:
        self.code = code
        super().__init__(
            "JSON-RPC request failed",
            stage=stage,
            process_exit_code=process_exit_code,
            stderr_summary=stderr_summary,
            rpc_code=code,
            rpc_message=message,
        )


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
        self._stderr_lines: deque[str] = deque(maxlen=12)
        self._last_parse_error: json.JSONDecodeError | None = None

    @staticmethod
    def discover_codex_executable() -> Path:
        probes = {
            name: shutil.which(name) for name in ("codex", "codex.exe", "codex.cmd")
        }
        for name in ("codex.exe", "codex", "codex.cmd"):
            if probes[name]:
                return Path(probes[name]).resolve()

        candidates: list[Path] = []
        local_app_data = os.environ.get("LOCALAPPDATA")
        roaming_app_data = os.environ.get("APPDATA")
        user_profile = os.environ.get("USERPROFILE")
        if local_app_data:
            local_root = Path(local_app_data)
            codex_bin = local_root / "OpenAI" / "Codex" / "bin"
            if codex_bin.is_dir():
                candidates.extend(codex_bin.glob("*/codex.exe"))
                candidates.extend(codex_bin.glob("codex.exe"))
            candidates.extend(
                (local_root / "npm" / name) for name in ("codex.cmd", "codex.exe")
            )
        if roaming_app_data:
            npm_root = Path(roaming_app_data) / "npm"
            candidates.extend(npm_root / name for name in ("codex.cmd", "codex.exe"))
        if user_profile:
            npm_root = Path(user_profile) / ".npm-global" / "bin"
            candidates.extend(npm_root / name for name in ("codex.cmd", "codex.exe"))

        existing = [candidate.resolve() for candidate in candidates if candidate.is_file()]
        if existing:
            return max(existing, key=lambda candidate: candidate.stat().st_mtime)
        cause = FileNotFoundError(
            "codex executable was not found in PATH or known per-user install locations"
        )
        raise AppServerError(
            "找不到 codex 命令，请先安装并登录 Codex CLI",
            stage="discover_codex",
            original=cause,
        ) from cause

    @classmethod
    def _default_command(cls) -> list[str] | str:
        try:
            executable = cls.discover_codex_executable()
        except AppServerError:
            cls._log_runtime_environment(None)
            raise
        cls._log_runtime_environment(executable)
        if executable.suffix.lower() in {".cmd", ".bat"} and os.name == "nt":
            command = f'"{executable}" app-server --listen stdio://'
        else:
            command = [str(executable), "app-server", "--listen", "stdio://"]
        LOGGER.info("Codex executable discovered: %s", executable)
        return command

    @staticmethod
    def _log_runtime_environment(discovered: Path | None) -> None:
        path_entries = {
            os.path.normcase(os.path.abspath(entry))
            for entry in os.environ.get("PATH", "").split(os.pathsep)
            if entry
        }
        codex_dir_in_path = bool(
            discovered
            and os.path.normcase(os.path.abspath(str(discovered.parent))) in path_entries
        )
        LOGGER.info(
            "Runtime environment: frozen=%s executable=%s cwd=%s "
            "PATH_has_codex_dir=%s USERPROFILE=%s APPDATA=%s LOCALAPPDATA=%s",
            bool(getattr(sys, "frozen", False)),
            sys.executable,
            os.getcwd(),
            codex_dir_in_path,
            bool(os.environ.get("USERPROFILE")),
            bool(os.environ.get("APPDATA")),
            bool(os.environ.get("LOCALAPPDATA")),
        )
        LOGGER.info(
            "Codex PATH probes: codex=%s codex.exe=%s codex.cmd=%s",
            shutil.which("codex"),
            shutil.which("codex.exe"),
            shutil.which("codex.cmd"),
        )

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process and self._process.poll() is None else None

    def start(self) -> None:
        with self._start_lock:
            if self._closed.is_set():
                raise AppServerError(
                    "Codex App Server client is closed", stage="spawn_app_server"
                )
            if self._process and self._process.poll() is None:
                return
            self._stopping.clear()
            self._stderr_lines.clear()
            self._last_parse_error = None
            command = self.command or self._default_command()
            uses_command_shell = isinstance(command, str)
            flags = (
                getattr(subprocess, "CREATE_NO_WINDOW", 0)
                if os.name == "nt" and not uses_command_shell
                else 0
            )
            startupinfo = None
            if os.name == "nt" and uses_command_shell:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
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
                    shell=uses_command_shell,
                    startupinfo=startupinfo,
                )
            except OSError as exc:
                raise AppServerError(
                    "无法启动 Codex App Server",
                    stage="spawn_app_server",
                    original=exc,
                ) from exc
            threading.Thread(
                target=self._read_stdout, name="codex-app-server", daemon=True
            ).start()
            threading.Thread(
                target=self._drain_stderr,
                name="codex-app-server-stderr",
                daemon=True,
            ).start()
            LOGGER.info("App Server spawned: pid=%s", self._process.pid)
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
                    stage="initialize_request",
                )
                LOGGER.info("initialize: OK")
                self._send(
                    {"method": "initialized", "params": {}},
                    stage="initialized_notification",
                )
                LOGGER.info("initialized notification: OK")
            except Exception:
                self._close_process()
                raise

    def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        stage: str,
    ) -> dict[str, Any]:
        last_error: AppServerError | None = None
        for attempt in range(2):
            if self._closed.is_set():
                raise AppServerError("Codex App Server client is closed", stage=stage)
            try:
                self.start()
                result = self._round_trip(method, params, stage=stage)
                LOGGER.info("%s: OK", method)
                return result
            except AppServerRpcError:
                raise
            except AppServerError as exc:
                last_error = exc
                self._close_process()
                if attempt == 0 and not self._closed.is_set():
                    time.sleep(0.25)
            except OSError as exc:
                last_error = self._error(
                    stage, "App Server I/O failed", original=exc
                )
                self._close_process()
                if attempt == 0 and not self._closed.is_set():
                    time.sleep(0.25)
        assert last_error is not None
        raise last_error

    def read_account(self) -> dict[str, Any]:
        return self.request(
            "account/read", {"refreshToken": False}, stage="account_read"
        )

    def read_rate_limits(self) -> dict[str, Any]:
        return self.request("account/rateLimits/read", stage="rate_limits_read")

    def close(self) -> None:
        self._closed.set()
        self._close_process()

    def _close_process(self) -> None:
        with self._start_lock:
            process = self._process
            self._process = None
            self._stopping.set()
            self._fail_pending(
                AppServerError(
                    "Codex App Server stopped",
                    stage="transport",
                    process_exit_code=process.poll() if process else None,
                    stderr_summary=self._stderr_summary(),
                )
            )
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
            LOGGER.info("Codex App Server stopped (exit_code=%s)", process.returncode)

    def __enter__(self) -> CodexAppServerClient:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _round_trip(
        self,
        method: str,
        params: dict[str, Any] | None,
        *,
        stage: str,
    ) -> dict[str, Any]:
        with self._pending_lock:
            request_id = self._next_id
            self._next_id += 1
            response_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=1)
            self._pending[request_id] = response_queue
        message: dict[str, Any] = {"id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        try:
            self._send(message, stage=stage)
            response = response_queue.get(timeout=self.timeout)
        except queue.Empty as exc:
            if self._last_parse_error is not None:
                parse_error = self._last_parse_error
                raise self._error(
                    "response_parse",
                    f"Malformed JSON while waiting for {method}",
                    original=parse_error,
                ) from parse_error
            raise self._error(
                stage,
                f"Codex App Server request timed out: {method}",
                original=exc,
            ) from exc
        finally:
            with self._pending_lock:
                self._pending.pop(request_id, None)
        if "_transport_error" in response:
            transport = response["_transport_error"]
            if isinstance(transport, AppServerError):
                raise self._error(
                    stage,
                    f"Transport failed during {method}",
                    original=transport,
                ) from transport
            cause = RuntimeError(redact(str(transport)))
            raise self._error(
                stage, f"Transport failed during {method}", original=cause
            ) from cause
        if "error" in response:
            error = response.get("error") or {}
            raise AppServerRpcError(
                error.get("code"),
                error.get("message") or "JSON-RPC error",
                stage=stage,
                process_exit_code=self._process_exit_code(),
                stderr_summary=self._stderr_summary(),
            )
        result = response.get("result")
        if not isinstance(result, dict):
            cause = TypeError(
                f"{method} result must be an object, got {type(result).__name__}"
            )
            raise self._error(
                "response_parse",
                f"Invalid JSON-RPC result for {method}",
                original=cause,
            ) from cause
        return result

    def _send(self, message: dict[str, Any], *, stage: str) -> None:
        process = self._process
        if not process or process.poll() is not None or not process.stdin:
            cause = BrokenPipeError("Codex App Server process is not running")
            raise self._error(
                stage, "Codex App Server is not running", original=cause
            ) from cause
        encoded = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        with self._write_lock:
            try:
                process.stdin.write(encoded + "\n")
                process.stdin.flush()
            except OSError as exc:
                raise self._error(
                    stage, "Failed to write to Codex App Server", original=exc
                ) from exc

    def _read_stdout(self) -> None:
        process = self._process
        if not process or not process.stdout:
            return
        try:
            for line in process.stdout:
                try:
                    message = json.loads(line)
                except json.JSONDecodeError as exc:
                    self._last_parse_error = exc
                    LOGGER.warning(
                        "response_parse: ignored malformed App Server output (%s)",
                        redact(str(exc)),
                    )
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
                        self.notification_handler(
                            method, params if isinstance(params, dict) else {}
                        )
                    except Exception as exc:
                        LOGGER.error(
                            "Notification handler failed for %s\n%s",
                            method,
                            redact("".join(traceback.format_exception(exc))),
                        )
        finally:
            if not self._stopping.is_set():
                try:
                    process.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    pass
                error = self._error(
                    "transport",
                    "Codex App Server disconnected",
                    process=process,
                )
                LOGGER.warning("%s", error)
                self._fail_pending(error)

    def _drain_stderr(self) -> None:
        process = self._process
        if not process or not process.stderr:
            return
        for line in process.stderr:
            safe_line = redact(line.strip())
            safe_line = re.sub(
                r"(?<![\\/])[A-Za-z0-9_.-]{32,}", "[REDACTED-LONG]", safe_line
            )[:500]
            if safe_line:
                self._stderr_lines.append(safe_line)
                LOGGER.debug("Codex App Server diagnostic captured")

    def _stderr_summary(self) -> str | None:
        if not self._stderr_lines:
            return None
        return " | ".join(self._stderr_lines)[-2000:]

    def _process_exit_code(
        self, process: subprocess.Popen[str] | None = None
    ) -> int | None:
        target = process or self._process
        return target.poll() if target else None

    def _error(
        self,
        stage: str,
        message: str,
        *,
        original: BaseException | None = None,
        process: subprocess.Popen[str] | None = None,
    ) -> AppServerError:
        return AppServerError(
            message,
            stage=stage,
            original=original,
            process_exit_code=self._process_exit_code(process),
            stderr_summary=self._stderr_summary(),
        )

    def _fail_pending(self, error: AppServerError) -> None:
        with self._pending_lock:
            queues = list(self._pending.values())
        for response_queue in queues:
            try:
                response_queue.put_nowait({"_transport_error": error})
            except queue.Full:
                pass
