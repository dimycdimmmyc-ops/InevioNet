param(
    [string]$RemoteHost = "192.168.1.100",
    [int]$RemotePort = 8080
)

Write-Host "=== P2P CONNECTION CHECK ===" -ForegroundColor Cyan
Write-Host ("Target: " + $RemoteHost + ":" + $RemotePort)
Write-Host ""

Write-Host "[1/4] Ping..." -ForegroundColor Yellow
$ping = Test-Connection -ComputerName $RemoteHost -Count 2 -Quiet -ErrorAction SilentlyContinue
if ($ping) {
    Write-Host "  [OK] host reachable" -ForegroundColor Green
} else {
    Write-Host "  [!!] host not reachable" -ForegroundColor Red
}
Write-Host ""

Write-Host ("[2/4] Port " + $RemotePort + "...") -ForegroundColor Yellow
$tcp = Test-NetConnection -ComputerName $RemoteHost -Port $RemotePort -WarningAction SilentlyContinue
if ($tcp.TcpTestSucceeded) {
    Write-Host "  [OK] port open" -ForegroundColor Green
} else {
    Write-Host "  [!!] port closed" -ForegroundColor Red
}
Write-Host ""

Write-Host "[3/4] HTTP check..." -ForegroundColor Yellow
try {
    $url = "https://" + $RemoteHost + ":" + $RemotePort + "/api/me"
    $r = Invoke-WebRequest -Uri $url -UseBasicParsing -SkipCertificateCheck -TimeoutSec 5 -ErrorAction SilentlyContinue
    if ($r.StatusCode -eq 401 -or $r.StatusCode -eq 200) {
        Write-Host ("  [OK] InevioNet responding (HTTP " + $r.StatusCode + ")") -ForegroundColor Green
    }
} catch {
    Write-Host "  [--] cannot verify (cert issue)" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "[4/4] Multicast..." -ForegroundColor Yellow
try {
    $u = New-Object System.Net.Sockets.UdpClient
    $u.EnableBroadcast = $true
    $m = [System.Text.Encoding]::UTF8.GetBytes('{"type":"inevionet_probe"}')
    $u.Send($m, $m.Length, "224.0.0.251", 9555) | Out-Null
    $u.Close()
    Write-Host "  [OK] beacon sent" -ForegroundColor Green
} catch {
    Write-Host "  [!!] multicast failed" -ForegroundColor Red
}
Write-Host ""
Write-Host "=== DONE ===" -ForegroundColor Cyan