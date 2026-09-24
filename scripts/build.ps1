# Скрипт сборки InevioNet в standalone .exe
Write-Host "🔨 Начало сборки InevioNet..." -ForegroundColor Cyan

$pyinstallerCmd = "pyinstaller --noconfirm --onefile --windowed --name InevioNet --hidden-import cryptography --hidden-import flask --hidden-import flask_socketio --hidden-import websockets --add-data 'web/templates;web/templates' --add-data 'web/static;web/static' web/app.py"

Write-Host "Выполняется: $pyinstallerCmd" -ForegroundColor Yellow
Invoke-Expression $pyinstallerCmd

if (Test-Path "$Root\dist\InevioNet.exe") {
    $size = [math]::Round((Get-Item "$Root\dist\InevioNet.exe").Length / 1MB, 2)
    Write-Host "✅ Сборка успешна!" -ForegroundColor Green
    Write-Host "📦 Файл: $Root\dist\InevioNet.exe ($size MB)" -ForegroundColor Cyan
    Write-Host "🚀 Запустите InevioNet.exe для запуска Web Dashboard на порту 8080" -ForegroundColor Cyan
} else {
    Write-Host "❌ Ошибка сборки. Проверьте логи выше." -ForegroundColor Red
}
