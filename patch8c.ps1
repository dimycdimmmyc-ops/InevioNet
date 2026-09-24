# Patch 8c v2: Visual C++ Build Tools (ASCII only)
$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  VISUAL C++ BUILD TOOLS INSTALLER" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Size: ~2 GB, Time: 10-15 min" -ForegroundColor Yellow
Write-Host ""

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "[!!] Need admin rights!" -ForegroundColor Red
    Write-Host "Run: Start-Process powershell -Verb RunAs -ArgumentList '-File E:\InevioNet\patch8c.ps1'" -ForegroundColor Yellow
    return
}

$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (Test-Path $vswhere) {
    $installs = & $vswhere -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2>$null
    if ($installs) {
        Write-Host "[--] VC++ already installed:" -ForegroundColor Yellow
        Write-Host "     $installs" -ForegroundColor Gray
        Write-Host ""
        Write-Host "Testing bleson..." -ForegroundColor Cyan
        python -c "from bleson import get_provider; print('OK')" 2>&1
        return
    }
}

Write-Host "[1/3] Downloading installer..." -ForegroundColor Cyan
$vsInstaller = Join-Path $env:TEMP "vs_buildtools.exe"
$url = "https://aka.ms/vs/17/release/vs_buildtools.exe"

try {
    Invoke-WebRequest -Uri $url -OutFile $vsInstaller -TimeoutSec 300
    Write-Host "[OK] Downloaded: $([math]::Round((Get-Item $vsInstaller).Length / 1MB, 1)) MB" -ForegroundColor Green
} catch {
    Write-Host "[!!] Download failed: $_" -ForegroundColor Red
    Write-Host "Manual: $url" -ForegroundColor Yellow
    return
}

Write-Host "[2/3] Installing VC++ (10-15 min)..." -ForegroundColor Cyan
Write-Host "     DO NOT CLOSE THIS WINDOW" -ForegroundColor Yellow

$arguments = @(
    "--quiet", "--wait", "--norestart", "--nocache",
    "--installPath", "C:\BuildTools",
    "--add", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
    "--add", "Microsoft.VisualStudio.Component.Windows11SDK.22000"
)

$proc = Start-Process -FilePath $vsInstaller -ArgumentList $arguments -Wait -PassThru

if ($proc.ExitCode -eq 0 -or $proc.ExitCode -eq 3010) {
    Write-Host "[OK] VC++ installed" -ForegroundColor Green
} else {
    Write-Host "[!!] Install failed with code $($proc.ExitCode)" -ForegroundColor Red
    return
}

Write-Host "[3/3] Installing Python packages..." -ForegroundColor Cyan
python -m pip install bleson pybluez2

Write-Host ""
Write-Host "Done!" -ForegroundColor Green
Write-Host "Restart PowerShell and test:" -ForegroundColor Cyan
Write-Host "  python -c \"from bleson import get_provider; print('OK')\"" -ForegroundColor Gray