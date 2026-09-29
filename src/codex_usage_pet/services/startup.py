from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

APP_NAME = "RitaDesktopPet"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def startup_command() -> str:
    if getattr(sys, "frozen", False):
        return subprocess.list2cmdline([str(Path(sys.executable).resolve())])
    python = Path(sys.executable)
    pythonw = python.with_name("pythonw.exe") if os.name == "nt" else python
    entry = Path(sys.argv[0]).resolve()
    return subprocess.list2cmdline([str(pythonw), str(entry)])


class StartupManager:
    def __init__(self, registry: object | None = None) -> None:
        if registry is None and os.name == "nt":
            import winreg

            registry = winreg
        self.registry = registry

    @property
    def supported(self) -> bool:
        return self.registry is not None

    def is_enabled(self) -> bool:
        if not self.registry:
            return False
        try:
            with self.registry.OpenKey(
                self.registry.HKEY_CURRENT_USER, RUN_KEY, 0, self.registry.KEY_READ
            ) as key:
                value, _ = self.registry.QueryValueEx(key, APP_NAME)
            return bool(value)
        except OSError:
            return False

    def set_enabled(self, enabled: bool) -> None:
        if not self.registry:
            raise RuntimeError("开机启动仅支持 Windows")
        with self.registry.CreateKeyEx(
            self.registry.HKEY_CURRENT_USER, RUN_KEY, 0, self.registry.KEY_SET_VALUE
        ) as key:
            if enabled:
                self.registry.SetValueEx(
                    key, APP_NAME, 0, self.registry.REG_SZ, startup_command()
                )
            else:
                try:
                    self.registry.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass

