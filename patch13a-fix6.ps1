# Patch 13a-fix6: fix topology stats + test shortest_path
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"
$orchPath = Join-Path $ProjectRoot "inevionet\orchestrator.py"

# Backup
$backupDir = Join-Path $ProjectRoot "_backup_topology_fix"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item $orchPath (Join-Path $backupDir "orchestrator.py") -Force
Write-Host "Backup: $backupDir\orchestrator.py" -ForegroundColor Cyan

$orch = [System.IO.File]::ReadAllText($orchPath, [System.Text.Encoding]::UTF8)
$orch = $orch -replace "`r`n", "`n"

# РќР°Р№С‚Рё _topology_loop Рё Р·Р°РјРµРЅРёС‚СЊ
$loopStart = $orch.IndexOf("    def _topology_loop(self):")
if ($loopStart -lt 0) {
    Write-Host "[!!] _topology_loop not found" -ForegroundColor Red
    exit 1
}

# РќР°Р№С‚Рё РєРѕРЅРµС† РјРµС‚РѕРґР° (РїРµСЂРµРґ def _forward_packet)
$loopEnd = $orch.IndexOf("    def _forward_packet(self, packet, next_hop):", $loopStart)
if ($loopEnd -lt 0) {
    Write-Host "[!!] end not found" -ForegroundColor Red
    exit 1
}

Write-Host "Loop: $loopStart .. $loopEnd" -ForegroundColor Cyan

$newLoop = @'
    def _topology_loop(self):
        # P13: topology every 30s (fixed stats)
        import time as _t
        while getattr(self, '_running', False):
            _t.sleep(30)
            if not getattr(self, '_running', False):
                break
            try:
                topo = self.enable_auto_topology()
                info = topo.build_from_scanner(min_quality=0.2)
                if info.get('success'):
                    # P13: get_stats from SAME object
                    stats = topo.get_stats()
                    logger.info('[Topology] nodes=%d edges=%d connected=%s',
                                stats.get('nodes', 0),
                                stats.get('edges', 0),
                                stats.get('is_connected', False))
                    # P13: test shortest_path if possible
                    try:
                        if hasattr(topo, 'shortest_path'):
                            nodes = list(getattr(topo, 'nodes', {}).keys())
                            if len(nodes) >= 2:
                                src = nodes[0]
                                dst = nodes[-1]
                                path = topo.shortest_path(src, dst)
                                if path:
                                    logger.info('[Topology] path %s -> %s: %s',
                                                src[:16], dst[:16],
                                                ' -> '.join(p[:12] for p in path))
                    except Exception as _e:
                        logger.debug('[Topology] shortest_path test: %s', _e)
            except Exception as e:
                logger.debug('[Topology] loop error: %s', e)

'@

$orch = $orch.Substring(0, $loopStart) + $newLoop + $orch.Substring($loopEnd)
Write-Host "[OK] _topology_loop replaced" -ForegroundColor Green

# Save + check
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($orchPath, $orch, $utf8)
Write-Host "[OK] orchestrator.py saved" -ForegroundColor Green

$syntax = python -c "import ast; ast.parse(open(r'$orchPath', encoding='utf-8').read()); print('OK')" 2>&1
Write-Host "Syntax: $syntax"

if ($syntax -notmatch "OK") {
    Write-Host "[!!] restoring backup" -ForegroundColor Red
    Copy-Item (Join-Path $backupDir "orchestrator.py") $orchPath -Force
    exit 1
}

Write-Host ""
Write-Host "=== PATCH 13a-fix6 DONE ===" -ForegroundColor Cyan
Write-Host "Restart: python -m web.app" -ForegroundColor Cyan