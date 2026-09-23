from __future__ import annotations

import ctypes
import os
import sys
import uuid
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QStandardPaths

SHORTCUT_FILENAME = "Codex Usage Pet.lnk"


class _GUID(ctypes.Structure):
    _fields_ = (
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    )

    @classmethod
    def parse(cls, value: str) -> "_GUID":
        raw = uuid.UUID(value).bytes_le
        return cls.from_buffer_copy(raw)


def desktop_path() -> Path:
    if os.name != "nt":
        raise RuntimeError("桌面快捷方式仅支持 Windows")
    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
    if not location:
        raise RuntimeError("无法取得当前用户桌面目录")
    return Path(location)


def _check_hresult(result: int, operation: str) -> None:
    if result < 0:
        raise OSError(f"{operation} 失败，HRESULT=0x{result & 0xFFFFFFFF:08X}")


def _com_method(
    interface: ctypes.c_void_p,
    index: int,
    restype: type[ctypes._SimpleCData],  # type: ignore[attr-defined]
    *argtypes: type[ctypes._SimpleCData],  # type: ignore[attr-defined]
):
    vtable = ctypes.cast(interface, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    prototype = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
    return prototype(vtable[index])


def write_shell_link(
    shortcut_path: Path,
    target_path: Path,
    working_directory: Path,
    icon_path: Path,
) -> None:
    """Create or replace a Unicode Windows Shell Link without extra packages."""

    if os.name != "nt":
        raise RuntimeError("桌面快捷方式仅支持 Windows")

    ole32 = ctypes.WinDLL("ole32", use_last_error=True)
    ole32.CoInitializeEx.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
    ole32.CoInitializeEx.restype = ctypes.c_long
    ole32.CoCreateInstance.argtypes = (
        ctypes.POINTER(_GUID),
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(_GUID),
        ctypes.POINTER(ctypes.c_void_p),
    )
    ole32.CoCreateInstance.restype = ctypes.c_long
    ole32.CoUninitialize.argtypes = ()
    ole32.CoUninitialize.restype = None

    initialized = False
    shell_link = ctypes.c_void_p()
    persist_file = ctypes.c_void_p()
    try:
        result = ole32.CoInitializeEx(None, 0x2)  # COINIT_APARTMENTTHREADED
        changed_mode = ctypes.c_long(0x80010106).value
        if result not in (0, 1, changed_mode):
            _check_hresult(result, "CoInitializeEx")
        initialized = result in (0, 1)

        clsid_shell_link = _GUID.parse("00021401-0000-0000-C000-000000000046")
        iid_shell_link = _GUID.parse("000214F9-0000-0000-C000-000000000046")
        result = ole32.CoCreateInstance(
            ctypes.byref(clsid_shell_link),
            None,
            0x1,  # CLSCTX_INPROC_SERVER
            ctypes.byref(iid_shell_link),
            ctypes.byref(shell_link),
        )
        _check_hresult(result, "CoCreateInstance(IShellLinkW)")

        set_description = _com_method(shell_link, 7, ctypes.c_long, ctypes.c_wchar_p)
        set_working_directory = _com_method(shell_link, 9, ctypes.c_long, ctypes.c_wchar_p)
        set_icon_location = _com_method(
            shell_link, 17, ctypes.c_long, ctypes.c_wchar_p, ctypes.c_int
        )
        set_path = _com_method(shell_link, 20, ctypes.c_long, ctypes.c_wchar_p)

        _check_hresult(set_path(shell_link, str(target_path)), "IShellLinkW.SetPath")
        _check_hresult(
            set_working_directory(shell_link, str(working_directory)),
            "IShellLinkW.SetWorkingDirectory",
        )
        _check_hresult(
            set_icon_location(shell_link, str(icon_path), 0),
            "IShellLinkW.SetIconLocation",
        )
        _check_hresult(
            set_description(shell_link, "Codex Usage Pet"),
            "IShellLinkW.SetDescription",
        )

        iid_persist_file = _GUID.parse("0000010B-0000-0000-C000-000000000046")
        query_interface = _com_method(
            shell_link,
            0,
            ctypes.c_long,
            ctypes.POINTER(_GUID),
            ctypes.POINTER(ctypes.c_void_p),
        )
        _check_hresult(
            query_interface(shell_link, ctypes.byref(iid_persist_file), ctypes.byref(persist_file)),
            "IShellLinkW.QueryInterface(IPersistFile)",
        )
        save = _com_method(persist_file, 6, ctypes.c_long, ctypes.c_wchar_p, ctypes.c_int)
        _check_hresult(save(persist_file, str(shortcut_path), 1), "IPersistFile.Save")
    finally:
        for interface in (persist_file, shell_link):
            if interface.value:
                release = _com_method(interface, 2, ctypes.c_ulong)
                release(interface)
        if initialized:
            ole32.CoUninitialize()


class DesktopShortcutManager:
    def __init__(
        self,
        *,
        executable: Path | None = None,
        frozen: bool | None = None,
        desktop_provider: Callable[[], Path] = desktop_path,
        writer: Callable[[Path, Path, Path, Path], None] = write_shell_link,
    ) -> None:
        self._frozen = bool(getattr(sys, "frozen", False) if frozen is None else frozen)
        self._executable = (
            Path(sys.executable).resolve() if executable is None and self._frozen else executable
        )
        if self._executable is not None:
            self._executable = self._executable.resolve()
        self._desktop_provider = desktop_provider
        self._writer = writer

    @property
    def supported(self) -> bool:
        return os.name == "nt" and self._frozen and self._executable is not None

    @property
    def shortcut_path(self) -> Path:
        return self._desktop_provider() / SHORTCUT_FILENAME

    def is_created(self) -> bool:
        if not self.supported:
            return False
        try:
            return self.shortcut_path.is_file()
        except OSError:
            return False

    def create(self) -> Path:
        if not self.supported or self._executable is None:
            raise RuntimeError("请在冻结版 CodexUsagePet.exe 中创建桌面快捷方式")
        if not self._executable.is_file():
            raise FileNotFoundError(f"找不到当前程序：{self._executable}")
        shortcut = self.shortcut_path
        self._writer(shortcut, self._executable, self._executable.parent, self._executable)
        return shortcut

    def delete(self) -> bool:
        if not self.supported:
            raise RuntimeError("请在冻结版 CodexUsagePet.exe 中删除桌面快捷方式")
        shortcut = self.shortcut_path
        try:
            shortcut.unlink()
        except FileNotFoundError:
            return False
        return True
