<#
.SYNOPSIS
    InevioNet - полный срез проекта для AI-анализа.
.DESCRIPTION
    Собирает: мета, дерево, статистику, список файлов, импорты,
    вызовы, точки входа, data/, логи, сборку, процессы, содержимое,
    git diff, дерево зависимостей.
.PARAMETER RootPath
    Корень проекта. По умолчанию E:\InevioNet
.PARAMETER OutputFile
    Куда писать. По умолчанию snapshot_inevionet.txt в корне
.PARAMETER MaxFileSizeKB
    Лимит на файл для включения содержимого (по умолчанию 500 KB)
.PARAMETER MaxLogLines
    Сколько последних строк брать из каждого .log (по умолчанию 200)
.PARAMETER SkipContent
    Не включать содержимое файлов (только структура + мета)
#>

param(
    [string]$RootPath = "E:\InevioNet",
    [string]$OutputFile = "",
    [int]$MaxFileSizeKB = 500,
    [int]$MaxLogLines = 200,
    [switch]$SkipContent
)

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

# ================================================================
# КОРЕНЬ
# ================================================================
if (-not (Test-Path $RootPath)) {
    Write-Host "[!!] Проект не найден: $RootPath" -ForegroundColor Red
    exit 1
}
$RootPath = (Resolve-Path $RootPath).Path

if (-not $OutputFile) {
    $OutputFile = Join-Path $RootPath "snapshot_inevionet.txt"
}

# ================================================================
# ИСКЛЮЧЕНИЯ
# ================================================================
$ExcludeDirs = @(
    'node_modules', '.git', '.svn', '.hg', 'bin', 'obj', 'dist', 'build',
    '__pycache__', '.venv', 'venv', 'env', '.idea', '.vscode', 'packages',
    'target', 'out', 'coverage', '.next', '.nuxt', '.cache', 'vendor',
    'Debug', 'Release', 'x64', 'x86', '.vs', 'TestResults',
    'InevioNet_RELEASE', 'InevioNet_v1.0.0_portable',
    'tor', 'tls', 'logs', 'htmlcov', '.pytest_cache',
    'inevionet.egg-info', 'backups'
)

$ExcludeDirPatterns = @(
    '_backup_*',
    'backup_*',
    'InevioNet_RELEASE*',
    'InevioNet_v*_portable*'
)

$ExcludeFilePatterns = @(
    '*.exe', '*.dll', '*.so', '*.dylib', '*.bin', '*.iso', '*.img',
    '*.zip', '*.tar', '*.gz', '*.7z', '*.rar', '*.jar', '*.war',
    '*.mp3', '*.mp4', '*.avi', '*.mkv', '*.mov', '*.jpg', '*.jpeg',
    '*.png', '*.gif', '*.bmp', '*.ico', '*.webp',
    '*.pdf', '*.doc', '*.docx', '*.xls', '*.xlsx', '*.ppt', '*.pptx',
    '*.pyc', '*.pyo', '*.class', '*.o', '*.obj', '*.pdb', '*.lock',
    '*.tmp', '*.temp', '*.swp', '*.swo',
    'snapshot_*.txt', '*.bak', '*.bak_*', '*.broken'
)

$ImportantExtensions = @(
    '.py', '.ps1', '.psm1', '.psd1', '.bat', '.cmd', '.sh',
    '.html', '.htm', '.css', '.js', '.json', '.yaml', '.yml',
    '.toml', '.ini', '.cfg', '.conf', '.xml', '.md', '.txt',
    '.spec'
)

# ================================================================
# ФУНКЦИИ
# ================================================================
function Write-Section {
    param([string]$Title)
    $line = "=" * 100
    Add-Content -Path $OutputFile -Value "`n$line" -Encoding UTF8
    Add-Content -Path $OutputFile -Value "  $Title" -Encoding UTF8
    Add-Content -Path $OutputFile -Value "$line`n" -Encoding UTF8
}

function Write-SubSection {
    param([string]$Title)
    Add-Content -Path $OutputFile -Value "`n--- $Title ---`n" -Encoding UTF8
}

function Write-Line {
    param([string]$Text)
    Add-Content -Path $OutputFile -Value $Text -Encoding UTF8
}

function Test-ExcludedDir {
    param([string]$FullPath)
    $rel = $FullPath.Substring($RootPath.Length).TrimStart('\')
    if (-not $rel) { return $false }
    $parts = $rel -split '\\'
    foreach ($p in $parts) {
        if ($ExcludeDirs -contains $p) { return $true }
        foreach ($pat in $ExcludeDirPatterns) {
            if ($p -like $pat) { return $true }
        }
    }
    return $false
}

function Test-ExcludedFile {
    param([System.IO.FileInfo]$File)
    $name = $File.Name
    foreach ($pat in $ExcludeFilePatterns) {
        if ($name -like $pat) { return $true }
    }
    return $false
}

function Get-RelPath {
    param([string]$FullPath)
    return $FullPath.Substring($RootPath.Length).TrimStart('\')
}

function Format-Size {
    param([long]$Bytes)
    if ($Bytes -gt 1MB) { return "{0:N2} MB" -f ($Bytes / 1MB) }
    if ($Bytes -gt 1KB) { return "{0:N2} KB" -f ($Bytes / 1KB) }
    return "$Bytes B"
}

# ================================================================
# СБОР ФАЙЛОВ
# ================================================================
Write-Host "[*] Сканирую проект..." -ForegroundColor Cyan

$allFiles = Get-ChildItem -Path $RootPath -Recurse -File -Force -ErrorAction SilentlyContinue |
    Where-Object {
        if (Test-ExcludedDir $_.DirectoryName) { return $false }
        if (Test-ExcludedFile $_) { return $false }
        return $true
    }

$allDirs = Get-ChildItem -Path $RootPath -Recurse -Directory -Force -ErrorAction SilentlyContinue |
    Where-Object { -not (Test-ExcludedDir $_.FullName) }

Write-Host "[*] Файлов: $($allFiles.Count), папок: $($allDirs.Count)" -ForegroundColor Cyan

# ================================================================
# ОЧИСТКА ВЫХОДА
# ================================================================
"" | Out-File -FilePath $OutputFile -Encoding UTF8

# ================================================================
# 0. МЕТА
# ================================================================
Write-Host "[1/14] Мета..." -ForegroundColor Yellow
Write-Section "0. МЕТА"

Write-Line "Root:        $RootPath"
Write-Line "Timestamp:   $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Line "Host:        $env:COMPUTERNAME"
Write-Line "User:        $env:USERNAME"
Write-Line "OS:          $([System.Environment]::OSVersion.VersionString)"
Write-Line "PowerShell:  $($PSVersionTable.PSVersion)"
Write-Line ""

Write-SubSection "Python"
try {
    $py = & python --version 2>&1
    Write-Line "python:      $py"
    $pyPath = & python -c "import sys; print(sys.executable)" 2>&1
    Write-Line "executable:  $pyPath"
} catch { Write-Line "(python недоступен)" }

Write-SubSection "Venv"
$venvPath = Join-Path $RootPath "venv\Scripts\python.exe"
if (Test-Path $venvPath) {
    Write-Line "venv:        $venvPath"
    try {
        $vpy = & $venvPath --version 2>&1
        Write-Line "venv python: $vpy"
    } catch {}
} else {
    Write-Line "(venv не найден)"
}

Write-SubSection "Git"
if (Test-Path (Join-Path $RootPath ".git")) {
    Push-Location $RootPath
    try {
        Write-Line "branch:      $(git rev-parse --abbrev-ref HEAD 2>$null)"
        Write-Line "last commit: $(git log -1 --pretty=format:'%h %s (%an, %ad)' 2>$null)"
        Write-Line "status:"
        git status --short 2>$null | ForEach-Object { Write-Line "  $_" }
    } catch {}
    Pop-Location
} else {
    Write-Line "(не git-репозиторий)"
}

# ================================================================
# 1. ДЕРЕВО
# ================================================================
Write-Host "[2/14] Дерево папок..." -ForegroundColor Yellow
Write-Section "1. ДЕРЕВО ПАПОК"

function Show-Tree {
    param([string]$Path, [string]$Prefix = "", [int]$Depth = 0)
    if ($Depth -gt 10) { return }
    $items = Get-ChildItem -Path $Path -Force -ErrorAction SilentlyContinue |
        Where-Object {
            if ($_.PSIsContainer) { return -not (Test-ExcludedDir $_.FullName) }
            return -not (Test-ExcludedFile $_)
        } | Sort-Object { -not $_.PSIsContainer }, Name
    for ($i = 0; $i -lt $items.Count; $i++) {
        $item = $items[$i]
        $isLast = ($i -eq $items.Count - 1)
        $conn = if ($isLast) { "\-- " } else { "|-- " }
        $newPref = $Prefix + $(if ($isLast) { "    " } else { "|   " })
        if ($item.PSIsContainer) {
            Write-Line "$Prefix$conn[$($item.Name)]/"
            Show-Tree -Path $item.FullName -Prefix $newPref -Depth ($Depth + 1)
        } else {
            $size = Format-Size $item.Length
            Write-Line "$Prefix$conn$($item.Name)  ($size)"
        }
    }
}
Write-Line "$(Split-Path $RootPath -Leaf)/"
Show-Tree -Path $RootPath

# ================================================================
# 2. СТАТИСТИКА
# ================================================================
Write-Host "[3/14] Статистика..." -ForegroundColor Yellow
Write-Section "2. СТАТИСТИКА ПО РАСШИРЕНИЯМ"

Write-Line ("{0,-15} {1,8} {2,15}" -f "Extension", "Count", "Total Size")
Write-Line ("-" * 45)
$allFiles | Group-Object Extension | Sort-Object Count -Descending | Select-Object -First 40 | ForEach-Object {
    $total = ($_.Group | Measure-Object -Property Length -Sum).Sum
    Write-Line ("{0,-15} {1,8} {2,15}" -f $_.Name, $_.Count, (Format-Size $total))
}
Write-Line ""
Write-Line "TOTAL FILES: $($allFiles.Count)"
$grandTotal = ($allFiles | Measure-Object -Property Length -Sum).Sum
Write-Line "TOTAL SIZE:  $(Format-Size $grandTotal)"

# ================================================================
# 3. СПИСОК ФАЙЛОВ
# ================================================================
Write-Host "[4/14] Список файлов..." -ForegroundColor Yellow
Write-Section "3. ПОЛНЫЙ СПИСОК ФАЙЛОВ"

Write-Line ("{0,-70} {1,12} {2,20}" -f "Path", "Size", "Modified")
Write-Line ("-" * 105)
foreach ($f in $allFiles | Sort-Object FullName) {
    $rel = Get-RelPath $f.FullName
    if ($rel.Length -gt 68) { $rel = "..." + $rel.Substring($rel.Length - 65) }
    Write-Line ("{0,-70} {1,12} {2,20}" -f $rel, (Format-Size $f.Length), $f.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss"))
}

# ================================================================
# 4. ИМПОРТЫ
# ================================================================
Write-Host "[5/14] Импорты..." -ForegroundColor Yellow
Write-Section "4. АНАЛИЗ ИМПОРТОВ"

Write-SubSection "Python"
foreach ($py in $allFiles | Where-Object { $_.Extension -eq '.py' } | Sort-Object FullName) {
    $rel = Get-RelPath $py.FullName
    $imports = Select-String -Path $py.FullName -Pattern '^\s*(?:from\s+([\w\.]+)\s+import|import\s+([\w\.]+))' -ErrorAction SilentlyContinue |
        ForEach-Object {
            if ($_.Matches[0].Groups[1].Value) { $_.Matches[0].Groups[1].Value }
            else { $_.Matches[0].Groups[2].Value }
        } | Sort-Object -Unique
    if ($imports) {
        Write-Line "$rel :"
        foreach ($imp in $imports) { Write-Line "    -> $imp" }
    }
}

Write-SubSection "JavaScript/TypeScript"
foreach ($js in $allFiles | Where-Object { $_.Extension -in @('.js','.ts','.jsx','.tsx','.vue','.svelte') } | Sort-Object FullName) {
    $rel = Get-RelPath $js.FullName
    $imports = Select-String -Path $js.FullName -Pattern "(?:import|require)\s*\(?['\`"]([^'\`"]+)['\`"]" -ErrorAction SilentlyContinue |
        ForEach-Object { $_.Matches[0].Groups[1].Value } | Sort-Object -Unique
    if ($imports) {
        Write-Line "$rel :"
        foreach ($imp in $imports) { Write-Line "    -> $imp" }
    }
}

# ================================================================
# 5. ВЫЗОВЫ (быстрая версия)
# ================================================================
Write-Host "[6/14] Вызовы..." -ForegroundColor Yellow
Write-Section "5. АНАЛИЗ ВЫЗОВОВ (кто кого использует)"

Write-SubSection "Определённые классы/функции"
$definitions = @{}
foreach ($py in $allFiles | Where-Object { $_.Extension -eq '.py' } | Sort-Object FullName) {
    $rel = Get-RelPath $py.FullName
    $defs = Select-String -Path $py.FullName -Pattern '^\s*(?:class|def)\s+([A-Za-z_]\w*)' -ErrorAction SilentlyContinue |
        ForEach-Object { $_.Matches[0].Groups[1].Value } | Sort-Object -Unique
    if ($defs) {
        $definitions[$rel] = $defs
        Write-Line "$rel :"
        foreach ($d in $defs) { Write-Line "    def/class $d" }
    }
}

Write-SubSection "Использование (кто вызывает)"
$allNames = @()
foreach ($rel in $definitions.Keys) { $allNames += $definitions[$rel] }
$allNames = $allNames | Sort-Object -Unique

if ($allNames.Count -eq 0) {
    Write-Line "(нет определений)"
} else {
    $pattern = '\b(' + (($allNames | ForEach-Object { [regex]::Escape($_) }) -join '|') + ')\b'
    $regex = [regex]::new($pattern, 'Compiled')

    foreach ($py in $allFiles | Where-Object { $_.Extension -eq '.py' } | Sort-Object FullName) {
        $rel = Get-RelPath $py.FullName
        try {
            $content = [System.IO.File]::ReadAllText($py.FullName, [System.Text.Encoding]::UTF8)
        } catch { continue }
        if (-not $content) { continue }

        $matches = $regex.Matches($content)
        if ($matches.Count -eq 0) { continue }

        $used = @{}
        foreach ($m in $matches) {
            $name = $m.Groups[1].Value
            if ($definitions[$rel] -and $definitions[$rel] -contains $name) { continue }
            $used[$name] = $true
        }
        if ($used.Count -gt 0) {
            Write-Line "$rel :"
            foreach ($u in ($used.Keys | Sort-Object)) { Write-Line "    uses $u" }
        }
    }
}

# ================================================================
# 6. ТОЧКИ ВХОДА
# ================================================================
Write-Host "[7/14] Точки входа..." -ForegroundColor Yellow
Write-Section "6. ТОЧКИ ВХОДА"

Write-SubSection "Файлы с __main__"
foreach ($py in $allFiles | Where-Object { $_.Extension -eq '.py' } | Sort-Object FullName) {
    $rel = Get-RelPath $py.FullName
    $hasMain = Select-String -Path $py.FullName -Pattern 'if\s+__name__\s*==\s*["'']__main__["'']' -ErrorAction SilentlyContinue
    if ($hasMain) { Write-Line "  $rel" }
}

Write-SubSection "Ключевые entry-point файлы"
foreach ($f in @('run_app.py', 'web\app.py', 'inevionet\__init__.py', 'setup.py', 'InevioNet.spec', 'start.bat', 'START.bat')) {
    $p = Join-Path $RootPath $f
    if (Test-Path $p) {
        Write-Line "  $f  ($(Format-Size (Get-Item $p).Length))"
    }
}

# ================================================================
# 7. DATA
# ================================================================
Write-Host "[8/14] Состояние data/..." -ForegroundColor Yellow
Write-Section "7. СОСТОЯНИЕ data/"

$dataDir = Join-Path $RootPath "data"
if (Test-Path $dataDir) {
    Get-ChildItem $dataDir -Recurse -File -ErrorAction SilentlyContinue | Sort-Object FullName | ForEach-Object {
        $rel = Get-RelPath $_.FullName
        Write-Line "$rel  ($(Format-Size $_.Length))  $($_.LastWriteTime)"
        if ($_.Extension -eq '.json' -and $_.Length -lt 100KB) {
            try {
                $j = Get-Content $_.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
                if ($j -is [PSCustomObject]) {
                    Write-Line "    keys: $($j.PSObject.Properties.Name -join ', ')"
                } elseif ($j -is [Array]) {
                    Write-Line "    array of $($j.Count) items"
                }
            } catch {
                Write-Line "    (не JSON или ошибка парсинга)"
            }
        }
    }
} else {
    Write-Line "(нет папки data/)"
}

# ================================================================
# 8. ЛОГИ
# ================================================================
Write-Host "[9/14] Логи..." -ForegroundColor Yellow
Write-Section "8. ЛОГИ (последние $MaxLogLines строк)"

$logsDir = Join-Path $RootPath "logs"
if (Test-Path $logsDir) {
    Get-ChildItem $logsDir -File -Filter "*.log" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | ForEach-Object {
        Write-SubSection "$($_.Name)  ($(Format-Size $_.Length), $($_.LastWriteTime))"
        $tail = Get-Content $_.FullName -Tail $MaxLogLines -ErrorAction SilentlyContinue
        foreach ($line in $tail) { Write-Line $line }
    }
} else {
    Write-Line "(нет папки logs/)"
}

# ================================================================
# 9. СБОРКА
# ================================================================
Write-Host "[10/14] Сборка..." -ForegroundColor Yellow
Write-Section "9. СБОРКА (requirements, spec, setup)"

foreach ($f in @('requirements.txt', 'setup.py', 'InevioNet.spec', 'pyproject.toml', 'Pipfile')) {
    $p = Join-Path $RootPath $f
    if (Test-Path $p) {
        Write-SubSection $f
        try {
            $content = Get-Content $p -Raw -Encoding UTF8 -ErrorAction Stop
            Write-Line $content
        } catch {
            Write-Line "(не удалось прочитать)"
        }
    }
}

# ================================================================
# 10. ПРОЦЕССЫ И ПОРТЫ
# ================================================================
Write-Host "[11/14] Процессы и порты..." -ForegroundColor Yellow
Write-Section "10. ПРОЦЕССЫ И ПОРТЫ"

Write-SubSection "Процессы InevioNet/Python/Tor/I2P"
Get-Process -ErrorAction SilentlyContinue |
    Where-Object { $_.ProcessName -match 'python|inevionet|tor|i2p|java' } |
    Select-Object ProcessName, Id, StartTime, @{N='RAM_MB';E={[math]::Round($_.WorkingSet64/1MB,1)}} |
    Format-Table -AutoSize | Out-String | ForEach-Object { Write-Line $_ }

Write-SubSection "Слушающие порты (8080, 7656, 7657, 9050, 9555)"
try {
    Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalPort -in @(8080, 7656, 7657, 9050, 9555, 9556) } |
        Select-Object LocalAddress, LocalPort, OwningProcess, State |
        Format-Table -AutoSize | Out-String | ForEach-Object { Write-Line $_ }
} catch {
    netstat -ano | Select-String ":8080|:7656|:7657|:9050|:9555|:9556" | ForEach-Object { Write-Line $_ }
}

Write-SubSection "TLS сертификаты"
$tlsDir = Join-Path $RootPath "data\tls"
if (Test-Path $tlsDir) {
    Get-ChildItem $tlsDir -File | ForEach-Object {
        Write-Line "$($_.Name)  ($(Format-Size $_.Length))  $($_.LastWriteTime)"
    }
} else {
    Write-Line "(нет data\tls\)"
}

# ================================================================
# 11. СОДЕРЖИМОЕ
# ================================================================
if (-not $SkipContent) {
    Write-Host "[12/14] Содержимое файлов..." -ForegroundColor Yellow
    Write-Section "11. СОДЕРЖИМОЕ ФАЙЛОВ"

    $contentFiles = $allFiles | Where-Object {
        $ext = $_.Extension.ToLower()
        $name = $_.Name.ToLower()
        if ($name -in @('dockerfile','makefile','rakefile','gemfile','procfile')) { return $true }
        if ($name -like '.env*' -or $name -like '.git*' -or $name -like '.editorconfig') { return $true }
        return $ImportantExtensions -contains $ext
    } | Sort-Object FullName

    Write-Line "Файлов к включению: $($contentFiles.Count)"
    Write-Line ""

    $idx = 0
    foreach ($f in $contentFiles) {
        $idx++
        $rel = Get-RelPath $f.FullName
        $sizeKB = [math]::Round($f.Length / 1KB, 2)
        Write-SubSection "[$idx/$($contentFiles.Count)] $rel  ($sizeKB KB)"

        if ($f.Length -gt ($MaxFileSizeKB * 1KB)) {
            Write-Line ">>> ФАЙЛ СЛИШКОМ БОЛЬШОЙ ($sizeKB KB) - SKIPPED. Первые 50 строк: <<<"
            Get-Content $f.FullName -TotalCount 50 -ErrorAction SilentlyContinue | ForEach-Object { Write-Line $_ }
        } else {
            try {
                $content = Get-Content $f.FullName -Raw -Encoding UTF8 -ErrorAction Stop
                if ($content) { Write-Line $content } else { Write-Line "(пустой файл)" }
            } catch {
                Write-Line "(бинарный или нечитаемый)"
            }
        }
        Write-Line ""
    }
}

# ================================================================
# 12. GIT DIFF
# ================================================================
Write-Host "[13/14] Git diff..." -ForegroundColor Yellow
Write-Section "12. GIT DIFF --STAT"

if (Test-Path (Join-Path $RootPath ".git")) {
    Push-Location $RootPath
    try {
        git diff --stat 2>$null | ForEach-Object { Write-Line $_ }
        Write-Line ""
        git diff --cached --stat 2>$null | ForEach-Object { Write-Line $_ }
    } catch {}
    Pop-Location
} else {
    Write-Line "(не git)"
}

# ================================================================
# 13. ДЕРЕВО ЗАВИСИМОСТЕЙ
# ================================================================
Write-Host "[14/14] Дерево зависимостей..." -ForegroundColor Yellow
Write-Section "13. ДЕРЕВО ЗАВИСИМОСТЕЙ МОДУЛЕЙ"

Write-SubSection "InevioNet внутренние импорты"
foreach ($py in $allFiles | Where-Object { $_.Extension -eq '.py' } | Sort-Object FullName) {
    $rel = Get-RelPath $py.FullName
    $inevioImports = Select-String -Path $py.FullName -Pattern '^\s*(?:from|import)\s+(inevionet[\w\.]*)' -ErrorAction SilentlyContinue |
        ForEach-Object { $_.Matches[0].Groups[1].Value } | Sort-Object -Unique
    if ($inevioImports) {
        Write-Line "$rel :"
        foreach ($imp in $inevioImports) { Write-Line "    -> $imp" }
    }
}

# ================================================================
# ЗАВЕРШЕНИЕ
# ================================================================
Write-Section "END OF SNAPSHOT"
Write-Line "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Line "Sections: 0-13"

$size = (Get-Item $OutputFile).Length
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host " SNAPSHOT ГОТОВ" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host " File:   $OutputFile" -ForegroundColor Cyan
Write-Host " Size:   $(Format-Size $size)" -ForegroundColor Cyan
Write-Host " Files:  $($allFiles.Count)" -ForegroundColor Cyan
Write-Host " Dirs:   $($allDirs.Count)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Если > 5 MB - скинь частями (секции 0-6, 7-13)." -ForegroundColor Yellow
Write-Host "Или запусти с -SkipContent для быстрой структуры." -ForegroundColor Yellow
Write-Host ""