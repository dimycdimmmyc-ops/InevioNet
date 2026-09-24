# Patch 1: evolution/genome.py - add 7 new genes
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"
$BackupDir = Join-Path $ProjectRoot "_backup_genome"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

$genomePath = Join-Path $ProjectRoot "inevionet\evolution\genome.py"
Copy-Item $genomePath (Join-Path $BackupDir "genome.py") -Force
Write-Host "Backup: $BackupDir\genome.py"

$genome = [System.IO.File]::ReadAllText($genomePath, [System.Text.Encoding]::UTF8)

$oldFields = @"
    packet_size: int = 1400
    ttl: int = 25
    priority: int = 5
    clone_threshold: int = 3

    fitness: float = 0.0
"@

$newFields = @"
    packet_size: int = 1400
    ttl: int = 25
    priority: int = 5
    clone_threshold: int = 3

    penetration_strategy: str = "HTTP_Tunneling"
    masking_channel: str = "HTTP"
    industrial_protocol: str = "MQTT"
    stego_method: str = "HTTP_HEADERS"
    use_polymorphic: bool = False
    use_ambient: bool = False
    use_stego: bool = False

    fitness: float = 0.0
"@

if ($genome.Contains($oldFields)) {
    $genome = $genome.Replace($oldFields, $newFields)
    Write-Host "[OK] Fields added" -ForegroundColor Green
} else {
    Write-Host "[!!] Fields NOT found - check file structure" -ForegroundColor Yellow
}

$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($genomePath, $genome, $utf8)
Write-Host "[OK] genome.py saved" -ForegroundColor Green