# Patch 3: mycelium/engine.py - add get_spores() method
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"
$BackupDir = Join-Path $ProjectRoot "_backup_mycelium"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

$path = Join-Path $ProjectRoot "inevionet\mycelium\engine.py"
Copy-Item $path (Join-Path $BackupDir "engine.py") -Force
Write-Host "Backup: $BackupDir\engine.py"

$content = [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)
$content = $content -replace "`r`n", "`n"
$content = $content -replace "`r", "`n"

# Проверка - уже патчено?
if ($content.Contains("def get_spores")) {
    Write-Host "[!!] get_spores already added" -ForegroundColor Yellow
} else {
    # Ищем "def get_stats(self):" внутри класса MyceliumEngine
    $oldStats = "    def get_stats(self):`n" +
                "        with self._lock:`n" +
                "            base = dict(self.stats)"
    
    $newStats = @'
    def get_spores(self):
        """P13: СЃРїРёСЃРѕРє Р¶РёРІС‹С… СЃРїРѕСЂ РґР»СЏ UI/discovery."""
        try:
            alive = self.spores.get_alive()
            return [s.to_dict() for s in alive]
        except Exception:
            return []

    def get_stats(self):
        with self._lock:
            base = dict(self.stats)
'@
    
    if ($content.Contains($oldStats)) {
        $content = $content.Replace($oldStats, $newStats)
        Write-Host "[OK] get_spores() added" -ForegroundColor Green
    } else {
        Write-Host "[!!] get_stats() pattern not found" -ForegroundColor Yellow
        Write-Host "Looking for alternative pattern..." -ForegroundColor Gray
        
        # Альтернативный поиск
        $altStats = "    def get_stats(self):"
        $pos = $content.IndexOf($altStats)
        if ($pos -gt 0) {
            $insert = @'
    def get_spores(self):
        """P13: СЃРїРёСЃРѕРє Р¶РёРІС‹С… СЃРїРѕСЂ РґР»СЏ UI/discovery."""
        try:
            alive = self.spores.get_alive()
            return [s.to_dict() for s in alive]
        except Exception:
            return []

'@
            $content = $content.Substring(0, $pos) + $insert + $content.Substring($pos)
            Write-Host "[OK] get_spores() inserted before get_stats()" -ForegroundColor Green
        }
    }
}

# Сохраняем
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($path, $content, $utf8)
Write-Host "[OK] mycelium/engine.py saved" -ForegroundColor Green

# Проверка синтаксиса
python -c "import ast; ast.parse(open(r'$path', encoding='utf-8').read()); print('OK')"