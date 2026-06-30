# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — one-folder, windowed build of PEAR.

Build:  pyinstaller pear.spec
Output: dist/PEAR/   (zip the folder to deploy to a machine without Python)
"""

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

hiddenimports = collect_submodules("pear")

# Trim heavy Qt modules PEAR never uses, plus unrelated frameworks.
excludes = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngine", "PySide6.Qt3DCore", "PySide6.Qt3DRender",
    "PySide6.Qt3DExtras", "PySide6.Qt3DInput", "PySide6.Qt3DAnimation",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets",
    "matplotlib", "tkinter", "PyQt5", "PyQt6", "scipy",
]

a = Analysis(
    ["pear/__main__.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PEAR",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PEAR",
)
