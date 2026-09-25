# patch53_fix.py - InevioNet: fix spec to onedir mode
import os

ROOT = r"E:\InevioNet"

SPEC = """# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

for pkg in ['flask', 'flask_socketio', 'eventlet', 'gevent',
            'cryptography', 'qrcode', 'pywifi', 'comtypes',
            'bleak', 'websockets', 'aiohttp', 'requests']:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

a = Analysis(
    ['run_app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas + [
        ('web/templates', 'web/templates'),
        ('web/static', 'web/static'),
        ('data', 'data'),
        ('docs', 'docs'),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'pytest'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='InevioNet',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='InevioNet',
)
"""

with open(os.path.join(ROOT, 'InevioNet.spec'), 'w', encoding='utf-8') as f:
    f.write(SPEC)
print('[OK] InevioNet.spec (onedir)')
print()
print('=' * 70)
print('  PATCH 53-fix DONE')
print('=' * 70)
print('Теперь: .\\build_installer.ps1 -Clean -Rebuild')