# Patch 8b v2: Tor Expert Bundle auto-install (ASCII only)
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"
$TorDir = Join-Path $ProjectRoot "tor"
$TorExe = Join-Path $TorDir "tor.exe"
$TorZip = Join-Path $env:TEMP "tor-expert-bundle.tar.gz"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  TOR EXPERT BUNDLE - AUTO INSTALL" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

if (Test-Path $TorExe) {
    Write-Host "[--] Tor already installed" -ForegroundColor Yellow
} else {
    New-Item -ItemType Directory -Path $TorDir -Force | Out-Null
    
    Write-Host "[1/3] Downloading Tor Expert Bundle..." -ForegroundColor Cyan
    $url = "https://archive.torproject.org/tor-package-archive/torbrowser/13.5.5/tor-expert-bundle-windows-x86_64-13.5.5.tar.gz"
    
    try {
        Invoke-WebRequest -Uri $url -OutFile $TorZip -TimeoutSec 120
        Write-Host "[OK] Downloaded: $([math]::Round((Get-Item $TorZip).Length / 1MB, 1)) MB" -ForegroundColor Green
    } catch {
        Write-Host "[!!] Download failed: $_" -ForegroundColor Red
        Write-Host "     Manual: $url" -ForegroundColor Yellow
        Write-Host "     Extract to: $TorDir" -ForegroundColor Yellow
        return
    }
    
    Write-Host "[2/3] Extracting..." -ForegroundColor Cyan
    tar -xzf $TorZip -C $TorDir
    
    if (Test-Path $TorExe) {
        Write-Host "[OK] Tor installed" -ForegroundColor Green
    } else {
        $found = Get-ChildItem -Path $TorDir -Recurse -Filter "tor.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) {
            $TorExe = $found.FullName
            Write-Host "[OK] Tor found: $TorExe" -ForegroundColor Green
        } else {
            Write-Host "[!!] tor.exe not found after extract" -ForegroundColor Red
            return
        }
    }
}

# torrc
$torrc = Join-Path $TorDir "torrc"
if (-not (Test-Path $torrc)) {
    $torrcContent = "SocksPort 9050`nControlPort 9051`nDataDirectory " + $TorDir + "\data`nLog notice file " + $TorDir + "\tor.log`n"
    [System.IO.File]::WriteAllText($torrc, $torrcContent, [System.Text.Encoding]::ASCII)
    Write-Host "[OK] torrc created" -ForegroundColor Green
}

# start_tor.bat
$torBat = Join-Path $ProjectRoot "start_tor.bat"
$batContent = "@echo off`r`necho Starting Tor...`r`nstart /B """" """ + $TorExe + """ -f """ + $torrc + """`r`necho Tor started on port 9050`r`ntimeout /t 3 >nul`r`n"
[System.IO.File]::WriteAllText($torBat, $batContent, [System.Text.Encoding]::ASCII)
Write-Host "[OK] start_tor.bat created" -ForegroundColor Green

Write-Host ""
Write-Host "[3/3] Starting Tor..." -ForegroundColor Cyan
Start-Process -FilePath $TorExe -ArgumentList "-f", $torrc -WindowStyle Hidden
Start-Sleep -Seconds 5

$torPort = Test-NetConnection -ComputerName 127.0.0.1 -Port 9050 -WarningAction SilentlyContinue
if ($torPort.TcpTestSucceeded) {
    Write-Host "[OK] Tor is running on 127.0.0.1:9050" -ForegroundColor Green
    Write-Host "     Click 'Check Tor' in UI after 30 sec" -ForegroundColor Cyan
} else {
    Write-Host "[!!] Tor not ready. Wait 30 sec and click 'Check Tor'" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done!" -ForegroundColor Green
Write-Host "  Tor dir: $TorDir" -ForegroundColor Cyan
Write-Host "  Launcher: $torBat" -ForegroundColor Cyan