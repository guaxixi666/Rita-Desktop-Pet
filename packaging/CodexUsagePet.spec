# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

project_root = Path(SPECPATH).parent

a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=[
        (str(project_root / "assets" / "rita" / "rita_sprite_sheet.png"), "assets/rita"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtWebEngineCore"],
    noarchive=False,
    optimize=1,
)
# The development PATH may contain Poppler's versioned ICU DLLs. Qt on Windows
# imports the unversioned ICU ABI supplied by System32; bundling Poppler's
# `icuuc.dll` causes WinError 127 at QtCore import time.
a.binaries = [
    item
    for item in a.binaries
    if Path(item[0]).name.lower() not in {"icuuc.dll", "icudt78.dll"}
]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CodexUsagePet",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=[str(project_root / "assets" / "codex_usage_pet.ico")],
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CodexUsagePet",
)
