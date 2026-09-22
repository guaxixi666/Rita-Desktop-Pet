from __future__ import annotations

from contextlib import contextmanager

from codex_usage_pet.services.startup import APP_NAME, StartupManager


class MemoryRegistry:
    HKEY_CURRENT_USER = object()
    KEY_READ = 1
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    @contextmanager
    def OpenKey(self, *_args):
        yield self

    @contextmanager
    def CreateKeyEx(self, *_args):
        yield self

    def QueryValueEx(self, _key, name: str):
        if name not in self.values:
            raise FileNotFoundError(name)
        return self.values[name], self.REG_SZ

    def SetValueEx(self, _key, name: str, _reserved: int, _kind: int, value: str):
        self.values[name] = value

    def DeleteValue(self, _key, name: str):
        if name not in self.values:
            raise FileNotFoundError(name)
        del self.values[name]


def test_startup_can_be_enabled_and_disabled() -> None:
    registry = MemoryRegistry()
    startup = StartupManager(registry)
    assert startup.is_enabled() is False
    startup.set_enabled(True)
    assert startup.is_enabled() is True
    assert APP_NAME in registry.values
    startup.set_enabled(False)
    assert startup.is_enabled() is False


def test_startup_disable_is_idempotent() -> None:
    startup = StartupManager(MemoryRegistry())
    startup.set_enabled(False)
    assert startup.is_enabled() is False

