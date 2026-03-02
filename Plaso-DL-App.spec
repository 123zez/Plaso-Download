# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['plaso_dl_app.py'],
    pathex=[],
    binaries=[],
    datas=[('src/plaso_dl/static', 'plaso_dl/static')],
    hiddenimports=['rich._unicode_data.unicode17-0-0'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Plaso-DL-App',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
