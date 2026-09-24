from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from codex_usage_pet.codex.app_server_client import (
    AppServerError,
    AppServerRpcError,
    CodexAppServerClient,
)

FAKE_SERVER = Path(__file__).with_name("fake_app_server.py")


def test_initializes_and_reads_account_and_limits() -> None:
    client = CodexAppServerClient([sys.executable, str(FAKE_SERVER)], timeout=2)
    try:
        assert client.read_account()["account"]["planType"] == "plus"
        assert client.read_rate_limits()["rateLimits"]["primary"]["usedPercent"] == 25
    finally:
        client.close()


def test_json_rpc_error_is_exposed() -> None:
    client = CodexAppServerClient(
        [sys.executable, str(FAKE_SERVER), "--error"], timeout=2
    )
    try:
        with pytest.raises(AppServerRpcError, match="test error") as raised:
            client.read_rate_limits()
        assert raised.value.stage == "rate_limits_read"
        assert raised.value.code == -32000
        assert raised.value.rpc_message == "test error"
    finally:
        client.close()


def test_unavailable_server_is_reported() -> None:
    client = CodexAppServerClient(["definitely-not-a-real-program-usage-pet"])
    with pytest.raises(AppServerError) as raised:
        client.start()
    assert raised.value.stage == "spawn_app_server"
    assert raised.value.original_type == "FileNotFoundError"
    assert isinstance(raised.value.__cause__, FileNotFoundError)


def test_missing_default_cli_is_reported_at_start_not_construction(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: None)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "profile"))
    client = CodexAppServerClient()
    with pytest.raises(AppServerError, match="找不到 codex") as raised:
        client.start()
    assert raised.value.stage == "discover_codex"
    assert raised.value.original_type == "FileNotFoundError"
    assert isinstance(raised.value.__cause__, FileNotFoundError)


def test_discovery_falls_back_to_codex_desktop_user_install(
    monkeypatch, tmp_path: Path
) -> None:
    executable = tmp_path / "OpenAI" / "Codex" / "bin" / "build-id" / "codex.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"placeholder")
    monkeypatch.setattr("shutil.which", lambda _name: None)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "profile"))
    assert CodexAppServerClient.discover_codex_executable() == executable.resolve()


def test_cmd_launcher_uses_windows_command_shell(monkeypatch, tmp_path: Path) -> None:
    launcher = tmp_path / "codex.cmd"
    launcher.write_text("@echo off", encoding="utf-8")
    monkeypatch.setattr(
        CodexAppServerClient,
        "discover_codex_executable",
        staticmethod(lambda: launcher),
    )
    command = CodexAppServerClient._default_command()
    assert command == f'"{launcher}" app-server --listen stdio://'


@pytest.mark.skipif(os.name != "nt", reason="Windows cmd launcher integration")
def test_cmd_launcher_can_spawn_app_server(monkeypatch, tmp_path: Path) -> None:
    launcher = tmp_path / "launcher with spaces" / "codex.cmd"
    launcher.parent.mkdir()
    launcher.write_text(
        f'@"{sys.executable}" "{FAKE_SERVER}"\n', encoding="utf-8"
    )
    monkeypatch.setattr(
        CodexAppServerClient,
        "discover_codex_executable",
        staticmethod(lambda: launcher),
    )
    client = CodexAppServerClient(timeout=2)
    try:
        assert client.read_account()["account"]["planType"] == "plus"
    finally:
        client.close()


def test_process_exit_and_redacted_stderr_are_preserved() -> None:
    client = CodexAppServerClient(
        [sys.executable, str(FAKE_SERVER), "--exit-on-initialize"], timeout=2
    )
    with pytest.raises(AppServerError) as raised:
        client.start()
    assert raised.value.stage == "initialize_request"
    assert raised.value.process_exit_code == 23
    assert "startup failed" in (raised.value.stderr_summary or "")
    assert "secret-value" not in str(raised.value)
    assert "[REDACTED]" in str(raised.value)
    assert raised.value.__cause__ is not None


def test_malformed_stdout_reports_response_parse_stage() -> None:
    client = CodexAppServerClient(
        [sys.executable, str(FAKE_SERVER), "--malformed"], timeout=0.1
    )
    try:
        with pytest.raises(AppServerError) as raised:
            client.start()
        assert raised.value.stage == "response_parse"
        assert raised.value.original_type == "JSONDecodeError"
    finally:
        client.close()


def test_close_cleans_up_child_process() -> None:
    client = CodexAppServerClient([sys.executable, str(FAKE_SERVER)], timeout=2)
    client.start()
    process = client._process
    assert process is not None and process.poll() is None
    client.close()
    assert process.poll() is not None
    assert client.pid is None
    with pytest.raises(AppServerError, match="closed"):
        client.start()
