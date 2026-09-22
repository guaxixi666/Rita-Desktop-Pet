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
        with pytest.raises(AppServerRpcError, match="test error"):
            client.read_rate_limits()
    finally:
        client.close()


def test_unavailable_server_is_reported() -> None:
    client = CodexAppServerClient(["definitely-not-a-real-program-usage-pet"])
    with pytest.raises(AppServerError):
        client.start()


def test_close_cleans_up_child_process() -> None:
    client = CodexAppServerClient([sys.executable, str(FAKE_SERVER)], timeout=2)
    client.start()
    process = client._process
    assert process is not None and process.poll() is None
    client.close()
    assert process.poll() is not None
    assert client.pid is None

