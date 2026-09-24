# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for building the Warsztat-Menager executable."""

import pathlib

block_cipher = None

project_root = pathlib.Path(__file__).resolve().parent


_def_datas = [
    ("11.ico", "."),
    ("themes.json", "."),
    ("settings_schema.json", "."),
    ("config.defaults.json", "."),
    ("config_profiles_seed.json", "."),
    ("config_profiles_snippet.json", "."),
    ("config.json", "."),
    ("wymagane_pliki.json", "."),
    ("data", "data"),
    ("grafiki", "grafiki"),
    ("avatars", "avatars"),
    (pathlib.Path("wm") / "data", "wm/data"),
]


def _collect_datas():
    resolved = []
    for src, dest in _def_datas:
        src_path = project_root / src
        if src_path.exists():
            resolved.append((str(src_path), dest))
    return resolved


a = Analysis(
    [str(project_root / "start.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=_collect_datas(),
    hiddenimports=["pystray._win32"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="WarsztatMenager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / "11.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="WarsztatMenager",
)
