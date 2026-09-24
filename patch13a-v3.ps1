# Patch 13a-v3: add relay methods + hook (fixed)
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"
$orchPath = Join-Path $ProjectRoot "inevionet\orchestrator.py"

# Backup
$backupDir = Join-Path $ProjectRoot "_backup_relay_v3"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item $orchPath (Join-Path $backupDir "orchestrator.py") -Force
Write-Host "Backup: $backupDir\orchestrator.py" -ForegroundColor Cyan

$orch = [System.IO.File]::ReadAllText($orchPath, [System.Text.Encoding]::UTF8)
$orch = $orch -replace "`r`n", "`n"

# РџСЂРѕРІРµСЂРєР° - СѓР¶Рµ РµСЃС‚СЊ?
if ($orch.Contains("def _try_relay_chain")) {
    Write-Host "[--] relay methods already exist" -ForegroundColor Yellow
} else {
    # РќР°Р№С‚Рё РјРµСЃС‚Рѕ
    $marker = "    def send_text(self, receiver, text, **kwargs):"
    $markerIdx = $orch.IndexOf($marker)
    if ($markerIdx -lt 0) {
        Write-Host "[!!] send_text marker NOT found" -ForegroundColor Red
        exit 1
    }
    Write-Host "Marker at: $markerIdx" -ForegroundColor Cyan

    # РњРµС‚РѕРґС‹
    $methodsCode = "    def _topology_loop(self):`n" +
"        # P13: topology every 30s`n" +
"        import time as _t`n" +
"        while getattr(self, '_running', False):`n" +
"            _t.sleep(30)`n" +
"            if not getattr(self, '_running', False):`n" +
"                break`n" +
"            try:`n" +
"                topo = self.enable_auto_topology()`n" +
"                info = topo.build_from_scanner(min_quality=0.2)`n" +
"                if info.get('success'):`n" +
"                    stats = topo.get_stats()`n" +
"                    logger.info('[Topology] nodes=%d edges=%d',`n" +
"                                stats.get('node_count', 0),`n" +
"                                stats.get('edge_count', 0))`n" +
"            except Exception as e:`n" +
"                logger.debug('[Topology] loop error: %s', e)`n" +
"`n" +
"    def _forward_packet(self, packet, next_hop):`n" +
"        # P13: forward relay packet`n" +
"        try:`n" +
"            target = self._resolve_target(next_hop)`n" +
"            if not target:`n" +
"                logger.warning('[Relay] no target for %s', next_hop)`n" +
"                return False`n" +
"            result = self.transport.send(`n" +
"                data=packet.to_bytes(),`n" +
"                protocol=self._map_protocol(packet.protocol or 'HTTPS'),`n" +
"                target=target)`n" +
"            if result.success:`n" +
"                logger.info('[Relay] Forwarded %s to %s (hop %d/%d)',`n" +
"                            packet.packet_id[:16], next_hop,`n" +
"                            packet.hop_count, packet.max_hops)`n" +
"                return True`n" +
"            return False`n" +
"        except Exception as e:`n" +
"            logger.error('[Relay] forward error: %s', e)`n" +
"            return False`n" +
"`n" +
"    def _try_relay_chain(self, packet, receiver):`n" +
"        # P13: try chain routing`n" +
"        try:`n" +
"            topo = self.enable_auto_topology()`n" +
"            path = None`n" +
"            if hasattr(topo, 'shortest_path'):`n" +
"                path = topo.shortest_path(self.node_id, receiver)`n" +
"            if not path or len(path) < 2:`n" +
"                return False, None`n" +
"            next_hop = path[1] if len(path) > 1 else None`n" +
"            if not next_hop or next_hop == receiver:`n" +
"                return False, None`n" +
"            packet.route_to = next_hop`n" +
"            packet.max_hops = max(2, len(path) - 1)`n" +
"            packet.origin = self.node_id`n" +
"            packet.metadata['full_path'] = path`n" +
"            logger.info('[Relay] Chain: %s', ' -> '.join(path))`n" +
"            target = self._resolve_target(next_hop)`n" +
"            if not target:`n" +
"                return False, None`n" +
"            result = self.transport.send(`n" +
"                data=packet.to_bytes(),`n" +
"                protocol=self._map_protocol(packet.protocol or 'HTTPS'),`n" +
"                target=target)`n" +
"            return result.success, path`n" +
"        except Exception as e:`n" +
"            logger.debug('[Relay] chain error: %s', e)`n" +
"            return False, None`n" +
"`n"

    $orch = $orch.Substring(0, $markerIdx) + $methodsCode + $orch.Substring($markerIdx)
    Write-Host "[OK] methods inserted" -ForegroundColor Green
}

# Hook topology loop in start()
$startMarker = "        logger.info(f`"InevioNet started: {self.node_id}`")"
if ($orch.Contains($startMarker)) {
    if ($orch.Contains("# P13: topology hook")) {
        Write-Host "[--] topology hook already exists" -ForegroundColor Yellow
    } else {
        $startHook = "        # P13: topology hook`n" +
"        try:`n" +
"            import threading as _th`n" +
"            _th.Thread(target=self._topology_loop, daemon=True, name='topology_loop').start()`n" +
"            logger.info('[Relay] topology loop started')`n" +
"        except Exception as _e:`n" +
"            logger.debug('[Relay] topology hook error: %s', _e)`n" +
"        logger.info(f`"InevioNet started: {self.node_id}`")"
        $orch = $orch.Replace($startMarker, $startHook)
        Write-Host "[OK] topology loop hooked" -ForegroundColor Green
    }
} else {
    Write-Host "[!!] start marker NOT found" -ForegroundColor Red
}

# Save
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($orchPath, $orch, $utf8)
Write-Host "[OK] orchestrator.py saved" -ForegroundColor Green

$syntax = python -c "import ast; ast.parse(open(r'$orchPath', encoding='utf-8').read()); print('OK')" 2>&1
Write-Host "Syntax: $syntax"

if ($syntax -notmatch "OK") {
    Write-Host "[!!] Syntax broken, restoring backup" -ForegroundColor Red
    Copy-Item (Join-Path $backupDir "orchestrator.py") $orchPath -Force
    Write-Host "[OK] restored" -ForegroundColor Green
    exit 1
}

Write-Host ""
Write-Host "=== PATCH 13a-v3 DONE ===" -ForegroundColor Cyan
Write-Host "Methods: _topology_loop, _forward_packet, _try_relay_chain" -ForegroundColor Yellow
Write-Host "Hook: topology loop in start()" -ForegroundColor Yellow
Write-Host "Restart: python -m web.app" -ForegroundColor Cyan