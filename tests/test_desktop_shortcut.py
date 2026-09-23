from __future__ import annotations

from pathlib import Path

import pytest

from codex_usage_pet.services.desktop_shortcut import (
    SHORTCUT_FILENAME,
    DesktopShortcutManager,
)


def test_development_mode_does_not_target_python(tmp_path: Path) -> None:
    manager = DesktopShortcutManager(
        executable=Path(__file__),
        frozen=False,
        desktop_provider=lambda: tmp_path,
    )
    assert manager.supported is False
    assert manager.is_created() is False
    with pytest.raises(RuntimeError, match="冻结版"):
        manager.create()


def test_create_uses_current_exe_working_directory_and_icon(tmp_path: Path) -> None:
    desktop = tmp_path / "中文桌面"
    desktop.mkdir()
    executable = tmp_path / "便携版" / "CodexUsagePet.exe"
    executable.parent.mkdir()
    executable.write_bytes(b"test executable")
    written: list[tuple[Path, Path, Path, Path]] = []

    def writer(shortcut: Path, target: Path, working: Path, icon: Path) -> None:
        written.append((shortcut, target, working, icon))
        shortcut.write_text(str(target), encoding="utf-8")

    manager = DesktopShortcutManager(
        executable=executable,
        frozen=True,
        desktop_provider=lambda: desktop,
        writer=writer,
    )
    shortcut = manager.create()

    assert shortcut == desktop / SHORTCUT_FILENAME
    assert written == [(shortcut, executable, executable.parent, executable)]
    assert manager.is_created() is True


def test_existing_shortcut_is_updated_not_duplicated(tmp_path: Path) -> None:
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    first = tmp_path / "first" / "CodexUsagePet.exe"
    second = tmp_path / "portable" / "CodexUsagePet.exe"
    for executable in (first, second):
        executable.parent.mkdir()
        executable.write_bytes(b"exe")

    def writer(shortcut: Path, target: Path, _working: Path, _icon: Path) -> None:
        shortcut.write_text(str(target), encoding="utf-8")

    for executable in (first, second):
        DesktopShortcutManager(
            executable=executable,
            frozen=True,
            desktop_provider=lambda: desktop,
            writer=writer,
        ).create()

    shortcuts = list(desktop.glob("*.lnk"))
    assert shortcuts == [desktop / SHORTCUT_FILENAME]
    assert shortcuts[0].read_text(encoding="utf-8") == str(second)


def test_delete_is_idempotent(tmp_path: Path) -> None:
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    executable = tmp_path / "CodexUsagePet.exe"
    executable.write_bytes(b"exe")

    def writer(shortcut: Path, _target: Path, _working: Path, _icon: Path) -> None:
        shortcut.touch()

    manager = DesktopShortcutManager(
        executable=executable,
        frozen=True,
        desktop_provider=lambda: desktop,
        writer=writer,
    )
    manager.create()
    assert manager.delete() is True
    assert manager.delete() is False
    assert manager.is_created() is False
