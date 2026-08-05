# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller recipe for YT-Pro.

Deliberately does NOT bundle yt-dlp.exe, ffmpeg.exe or spotdl.exe. Bundling them
would push the exe past 130 MB and — worse — freeze yt-dlp at build time, which
is exactly the failure mode ("stopped working after a few weeks") that the
runtime self-updater exists to prevent. The app fetches them into
%APPDATA%\\YT-Pro on first run and keeps them current from then on.
"""

from PyInstaller.utils.hooks import collect_data_files

# customtkinter ships its themes and assets as data files; without these the
# window opens unstyled or not at all.
datas = collect_data_files("customtkinter")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=["customtkinter"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # Nothing here is used, and each one adds tens of megabytes.
        "matplotlib", "numpy", "pandas", "scipy", "PIL.ImageQt",
        "PyQt5", "PySide2", "PySide6", "tkinter.test", "test", "unittest",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="YT-Pro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX-packed exes trip antivirus heuristics constantly
    console=False,      # GUI app — no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/ytpro.ico" if __import__("os").path.exists("assets/ytpro.ico") else None,
)
