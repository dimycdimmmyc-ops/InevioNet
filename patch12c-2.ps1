# Patch 12c-2: README + check script
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"
$DeployDir = Join-Path $ProjectRoot "deploy"

# check_connection.ps1
$checkPs = "param([string]`$RemoteHost = ""192.168.1.100"", [int]`$RemotePort = 8080)`r`n" +
"Write-Host ""=== P2P CONNECTION CHECK ===="" -ForegroundColor Cyan`r`n" +
"Write-Host ""Target: `$RemoteHost`:`$RemotePort""`r`n" +
"Write-Host ""`r`n[1/4] Ping..."" -ForegroundColor Yellow`r`n" +
"if (Test-Connection -ComputerName `$RemoteHost -Count 2 -Quiet) { Write-Host ""  [OK]"" -ForegroundColor Green } else { Write-Host ""  [!!] no ping"" -ForegroundColor Red }`r`n" +
"Write-Host ""`r`n[2/4] Port `$RemotePort..."" -ForegroundColor Yellow`r`n" +
"if ((Test-NetConnection -ComputerName `$RemoteHost -Port `$RemotePort -WarningAction SilentlyContinue).TcpTestSucceeded) { Write-Host ""  [OK]"" -ForegroundColor Green } else { Write-Host ""  [!!] closed"" -ForegroundColor Red }`r`n" +
"Write-Host ""`r`n[3/4] HTTP..."" -ForegroundColor Yellow`r`n" +
"try { `$r = Invoke-WebRequest -Uri ""https://`${RemoteHost}:`${RemotePort}/api/me"" -UseBasicParsing -SkipCertificateCheck -TimeoutSec 5 -ErrorAction SilentlyContinue; Write-Host ""  [OK] HTTP `$(`$r.StatusCode)"" -ForegroundColor Green } catch { Write-Host ""  [--] cannot verify"" -ForegroundColor Yellow }`r`n" +
"Write-Host ""`r`n[4/4] Multicast..."" -ForegroundColor Yellow`r`n" +
"try { `$u = New-Object System.Net.Sockets.UdpClient; `$u.EnableBroadcast = `$true; `$m = [System.Text.Encoding]::UTF8.GetBytes('{""type"":""inevionet_probe""}'); `$u.Send(`$m, `$m.Length, ""224.0.0.251"", 9555) | Out-Null; `$u.Close(); Write-Host ""  [OK] beacon sent"" -ForegroundColor Green } catch { Write-Host ""  [!!] `$_"" -ForegroundColor Red }`r`n" +
"Write-Host ""`r`nDONE"" -ForegroundColor Cyan`r`n"

$checkPath = Join-Path $DeployDir "check_connection.ps1"
[System.IO.File]::WriteAllText($checkPath, $checkPs, [System.Text.UTF8Encoding]::new($false))
Write-Host "[OK] check_connection.ps1" -ForegroundColor Green

# README.md (one line at a time)
$readmeLines = @(
    "# InevioNet - Deployment Guide",
    "",
    "## Quick Start",
    "",
    "### Step 1: Install Python on second PC",
    "Download from https://www.python.org/downloads/",
    "IMPORTANT: Check 'Add Python to PATH'",
    "",
    "### Step 2: Copy project",
    "Copy E:\InevioNet to second PC (without venv folder)",
    "",
    "### Step 3: Install",
    "Double-click: deploy\install_remote.bat",
    "",
    "### Step 4: Run",
    "Double-click: deploy\start_remote.bat",
    "Open: https://localhost:8080",
    "",
    "## P2P Connection",
    "",
    "1. Both PCs must be on same WiFi/LAN",
    "2. Wait 30 sec after both start",
    "3. They will auto-discover each other",
    "",
    "### Test from first PC",
    "cd deploy",
    "powershell -ExecutionPolicy Bypass -File check_connection.ps1 -RemoteHost 192.168.1.100",
    "",
    "## Troubleshooting",
    "",
    "Port 8080 busy:",
    "- Edit web/app.py, change port=8080 to 8081",
    "",
    "Firewall:",
    "- Settings > Firewall > Allow app > python.exe",
    "",
    "No connection:",
    "- Test-NetConnection <ip> -Port 8080",
    "- Check both PCs on same network",
    "",
    "## Optional: Tor / I2P",
    "",
    "Tor:",
    "- Download Tor Expert Bundle via VPN",
    "- Extract tor.exe to tor\ folder",
    "",
    "I2P:",
    "- Install from https://geti2p.net/",
    "- Enable SAM: http://127.0.0.1:7657/configclients",
    "",
    "## Sync between PCs",
    "",
    "deploy\sync.bat",
    "",
    "## Architecture",
    "",
    "PC1 (192.168.1.180)     PC2 (192.168.1.100)",
    "     :8080                    :8080",
    "       |                        |",
    "       +--- Multicast 9555 -----+",
    "       +--- WebRTC P2P ---------+",
    "       +--- I2P ---------------+",
    "",
    "All messages encrypted + signed."
)

$readmePath = Join-Path $DeployDir "README.md"
[System.IO.File]::WriteAllLines($readmePath, $readmeLines, [System.Text.UTF8Encoding]::new($false))
Write-Host "[OK] README.md" -ForegroundColor Green

Write-Host ""
Write-Host "=== FILES IN deploy\ ===" -ForegroundColor Cyan
Get-ChildItem $DeployDir | ForEach-Object { Write-Host "  $($_.Name)" -ForegroundColor White }
Write-Host ""
Write-Host "DONE. Test connection (self):" -ForegroundColor Green
Write-Host "  deploy\check_connection.ps1 -RemoteHost 127.0.0.1" -ForegroundColor White