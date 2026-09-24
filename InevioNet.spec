# -*- mode: python ; coding: utf-8 -*-
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
    hiddenimports=hiddenimports + [
        'engineio.async_drivers.threading',
        'engineio.async_drivers.eventlet',
        'engineio.async_drivers.gevent',
        'engineio.async_drivers._websocket_wsgi',
        'socketio',
        'engineio',
        'eventlet',
        'eventlet.hubs',
        'eventlet.hubs.epolls',
        'eventlet.hubs.kqueue',
        'eventlet.hubs.selects',
        'eventlet.green.threading',
        'eventlet.green.ssl',
        'flask_socketio',
    ],
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
