from pathlib import Path


project_root = Path(SPECPATH).parent
source_root = project_root / "src"
static_root = source_root / "game_script_dev" / "dashboard" / "static"
manifest_path = project_root / "packaging" / "windows" / "GameScriptDev.manifest"

a = Analysis(
    [str(source_root / "game_script_dev" / "operator_app.py")],
    pathex=[str(source_root)],
    binaries=[],
    datas=[(str(static_root), "game_script_dev/dashboard/static")],
    hiddenimports=["webview", "webview.platforms.edgechromium"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "cefpython3",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "webview.platforms.mshtml",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GameScriptDev",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    manifest=str(manifest_path),
    uac_admin=False,
    uac_uiaccess=False,
    contents_directory="_internal",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="GameScriptDev",
)
