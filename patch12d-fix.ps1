# Patch 12d-fix: fix spec file
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"

$specContent = "# -*- mode: python ; coding: utf-8 -*-`n" +
"`n" +
"from PyInstaller.utils.hooks import collect_submodules, collect_data_files`n" +
"`n" +
"hiddenimports = []`n" +
"hiddenimports += collect_submodules('flask')`n" +
"hiddenimports += collect_submodules('flask_socketio')`n" +
"hiddenimports += collect_submodules('engineio')`n" +
"hiddenimports += collect_submodules('socketio')`n" +
"hiddenimports += collect_submodules('eventlet')`n" +
"hiddenimports += ['inevionet', 'inevionet.network', 'inevionet.mycelium',`n" +
"                  'inevionet.evolution', 'inevionet.masking',`n" +
"                  'inevionet.steganography', 'inevionet.industrial',`n" +
"                  'inevionet.identity', 'inevionet.mesh', 'inevionet.symbiotic',`n" +
"                  'inevionet.ai', 'inevionet.capsule', 'inevionet.users']`n" +
"`n" +
"datas = []`n" +
"datas += collect_data_files('flask')`n" +
"datas += collect_data_files('flask_socketio')`n" +
"`n" +
"block_cipher = None`n" +
"`n" +
"a = Analysis(`n" +
"    ['run_app.py'],`n" +
"    pathex=[r'" + $ProjectRoot + "'],`n" +
"    binaries=[],`n" +
"    datas=datas,`n" +
"    hiddenimports=hiddenimports,`n" +
"    hookspath=[],`n" +
"    runtime_hooks=[],`n" +
"    excludes=['tkinter', 'matplotlib', 'numpy', 'PIL'],`n" +
"    win_no_prefer_redirects=False,`n" +
"    win_private_assemblies=False,`n" +
"    cipher=block_cipher,`n" +
"    noarchive=False,`n" +
")`n" +
"`n" +
"pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)`n" +
"`n" +
"exe = EXE(`n" +
"    pyz,`n" +
"    a.scripts,`n" +
"    a.binaries,`n" +
"    a.zipfiles,`n" +
"    a.datas,`n" +
"    [],`n" +
"    name='InevioNet',`n" +
"    debug=False,`n" +
"    bootloader_ignore_signals=False,`n" +
"    strip=False,`n" +
"    upx=True,`n" +
"    upx_exclude=[],`n" +
"    runtime_tmpdir=None,`n" +
"    console=True,`n" +
"    disable_windowed_traceback=False,`n" +
"    argv_emulation=False,`n" +
"    target_arch=None,`n" +
"    codesign_identity=None,`n" +
"    entitlements_file=None,`n" +
"    icon=None,`n" +
")`n"

$specPath = Join-Path $ProjectRoot "InevioNet.spec"
[System.IO.File]::WriteAllText($specPath, $specContent, [System.Text.UTF8Encoding]::new($false))
Write-Host "[OK] InevioNet.spec fixed" -ForegroundColor Green

# Show spec
Write-Host ""
Write-Host "=== SPEC CONTENT ===" -ForegroundColor Cyan
Get-Content $specPath | Select-Object -First 35
Write-Host "..."

# Now build
Write-Host ""
Write-Host "=== BUILDING ===" -ForegroundColor Cyan
Set-Location $ProjectRoot
& python -m PyInstaller InevioNet.spec --clean --noconfirm

if (Test-Path (Join-Path $ProjectRoot "dist\InevioNet.exe")) {
    Write-Host ""
    Write-Host "[OK] EXE built!" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[!!] EXE not created" -ForegroundColor Red
}