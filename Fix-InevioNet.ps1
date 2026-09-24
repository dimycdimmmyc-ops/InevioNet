$ErrorActionPreference = "Continue"
$ProjectRoot = "E:\InevioNet"

if (-not (Test-Path $ProjectRoot)) {
    Write-Host "[!!] Проект не найден: $ProjectRoot" -ForegroundColor Red
    exit 1
}
Set-Location $ProjectRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  INEVIONET FIX & RUN" -ForegroundColor Cyan
Write-Host "  Root: $ProjectRoot" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$appPath  = Join-Path $ProjectRoot "web\app.py"
$htmlPath = Join-Path $ProjectRoot "web\templates\index.html"

if (-not (Test-Path $appPath)) {
    Write-Host "[!!] Нет файла: $appPath" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $htmlPath)) {
    Write-Host "[!!] Нет файла: $htmlPath" -ForegroundColor Red
    exit 1
}

Write-Host "`n[1/4] Файлы на месте" -ForegroundColor Green
Write-Host "     app.py     $([math]::Round((Get-Item $appPath).Length/1KB,1)) KB" -ForegroundColor DarkGray
Write-Host "     index.html $([math]::Round((Get-Item $htmlPath).Length/1KB,1)) KB" -ForegroundColor DarkGray

Write-Host "`n[2/4] Проверка BOM..." -ForegroundColor Yellow

$bytes = [System.IO.File]::ReadAllBytes($appPath)
$hasBom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)

if ($hasBom) {
    Write-Host "     BOM обнаружен! Убираю..." -ForegroundColor Yellow
    $content = [System.IO.File]::ReadAllText($appPath)
    $content = $content.TrimStart([char]0xFEFF)
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($appPath, $content, $utf8)
    Write-Host "     BOM удалён из app.py" -ForegroundColor Green
} else {
    Write-Host "     BOM в app.py отсутствует" -ForegroundColor Green
}

$htmlBytes = [System.IO.File]::ReadAllBytes($htmlPath)
$htmlHasBom = ($htmlBytes.Length -ge 3 -and $htmlBytes[0] -eq 0xEF -and $htmlBytes[1] -eq 0xBB -and $htmlBytes[2] -eq 0xBF)
if ($htmlHasBom) {
    Write-Host "     BOM в index.html - убираю..." -ForegroundColor Yellow
    $htmlContent = [System.IO.File]::ReadAllText($htmlPath)
    $htmlContent = $htmlContent.TrimStart([char]0xFEFF)
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($htmlPath, $htmlContent, $utf8)
    Write-Host "     BOM удалён из index.html" -ForegroundColor Green
} else {
    Write-Host "     BOM в index.html отсутствует" -ForegroundColor Green
}

Write-Host "`n[3/4] Проверка синтаксиса Python..." -ForegroundColor Yellow

$checkResult = & python -c "import ast; ast.parse(open(r'$appPath', encoding='utf-8').read()); print('OK')" 2>&1

if ($checkResult -match 'OK') {
    Write-Host "     Синтаксис корректен" -ForegroundColor Green
} else {
    Write-Host "     Ошибка синтаксиса:" -ForegroundColor Red
    Write-Host "     $checkResult" -ForegroundColor Red
    exit 1
}

Write-Host "`n[4/4] Запуск сервера..." -ForegroundColor Green
Write-Host "     Ctrl+C - остановить" -ForegroundColor Yellow
Write-Host "     Браузер: https://localhost:8080" -ForegroundColor Yellow
Write-Host ""

Set-Location $ProjectRoot
& python -m web.app
