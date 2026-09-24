# Patch 13a-fix4-v2: precise insert with indent check
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"
$orchPath = Join-Path $ProjectRoot "inevionet\orchestrator.py"

# Backup
$backupDir = Join-Path $ProjectRoot "_backup_relay_v4v2"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item $orchPath (Join-Path $backupDir "orchestrator.py") -Force
Write-Host "Backup: $backupDir\orchestrator.py" -ForegroundColor Cyan

$orch = [System.IO.File]::ReadAllText($orchPath, [System.Text.Encoding]::UTF8)
$orch = $orch -replace "`r`n", "`n"

# === 1. Patch try_delivery ===
if ($orch.Contains("# P13: try relay chain first")) {
    Write-Host "[--] try_delivery already patched" -ForegroundColor Yellow
} else {
    $tryStart = $orch.IndexOf("        def try_delivery(alt, depth):")
    if ($tryStart -lt 0) {
        Write-Host "[!!] try_delivery NOT found" -ForegroundColor Red
    } else {
        Write-Host "try_delivery at: $tryStart" -ForegroundColor Cyan
        
        # РќР°Р№С‚Рё РїРµСЂРІС‹Р№ "proto = alt[" РїРѕСЃР»Рµ try_delivery
        $protoIdx = $orch.IndexOf("            proto = alt[", $tryStart)
        if ($protoIdx -ge 0) {
            $lineEnd = $orch.IndexOf("`n", $protoIdx)
            if ($lineEnd -gt 0) {
                # РџСЂРѕРІРµСЂРёС‚СЊ С‡С‚Рѕ СЃР»РµРґ. СЃС‚СЂРѕРєР° РёРјРµРµС‚ РѕС‚СЃС‚СѓРї >= 12 РїСЂРѕР±РµР»РѕРІ
                $after = $orch.Substring($lineEnd + 1, 30)
                if ($after -match "^\s{12,}") {
                    # Р’СЃС‚Р°РІРёС‚СЊ СЃ 16 РїСЂРѕР±РµР»Р°РјРё
                    $chainCode = "`n" +
"                # P13: try relay chain first`n" +
"                if proto not in ('I2P', 'MQTT', 'MODBUS', 'DNP3', 'OPCUA'):`n" +
"                    try:`n" +
"                        chain_ok, chain_path = self._try_relay_chain(packet, receiver)`n" +
"                        if chain_ok:`n" +
"                            if self.evolution:`n" +
"                                self.evolution.reward('protocol', proto, True)`n" +
"                            return True, 0.95`n" +
"                    except Exception as _ce:`n" +
"                        logger.debug('[Relay] chain try error: %s', _ce)`n"
                    
                    $orch = $orch.Substring(0, $lineEnd) + $chainCode + $orch.Substring($lineEnd)
                    Write-Host "[OK] try_delivery patched" -ForegroundColor Green
                } else {
                    Write-Host "[!!] indent check failed for try_delivery" -ForegroundColor Red
                }
            }
        }
    }
}

# === 2. Patch receive() ===
if ($orch.Contains("# P13: should I relay")) {
    Write-Host "[--] receive() already patched" -ForegroundColor Yellow
} else {
    $recvStart = $orch.IndexOf("    def receive(self, packet_data):")
    if ($recvStart -lt 0) {
        Write-Host "[!!] receive() NOT found" -ForegroundColor Red
    } else {
        Write-Host "receive() at: $recvStart" -ForegroundColor Cyan
        
        # РќР°Р№С‚Рё РїРѕСЃР»РµРґРЅРёР№ "packet = self._parse_packet" РІ С„СѓРЅРєС†РёРё receive
        # (РЅРµ РґРѕС…РѕРґСЏ РґРѕ СЃР»РµРґСѓСЋС‰РµРіРѕ def)
        $nextDef = $orch.IndexOf("`n    def ", $recvStart + 10)
        if ($nextDef -lt 0) { $nextDef = $orch.Length }
        
        # РСЃРєР°С‚СЊ РІСЃРµ РІС…РѕР¶РґРµРЅРёСЏ РІ РґРёР°РїР°Р·РѕРЅРµ
        $searchStart = $recvStart
        $parseIdx = -1
        while ($true) {
            $found = $orch.IndexOf("packet = self._parse_packet", $searchStart)
            if ($found -lt 0 -or $found -ge $nextDef) { break }
            $parseIdx = $found
            $searchStart = $found + 1
        }
        
        if ($parseIdx -ge 0) {
            $lineEnd = $orch.IndexOf("`n", $parseIdx)
            if ($lineEnd -gt 0) {
                # РџСЂРѕРІРµСЂРёС‚СЊ С‡С‚Рѕ СЃР»РµРґ. СЃС‚СЂРѕРєР° РЅР°С‡РёРЅР°РµС‚СЃСЏ СЃ 12 РїСЂРѕР±РµР»РѕРІ
                $after = $orch.Substring($lineEnd + 1, 30)
                if ($after -match "^\s{8,}") {
                    # Р’СЃС‚Р°РІРёС‚СЊ СЃ 12 РїСЂРѕР±РµР»Р°РјРё
                    $relayCode = "`n" +
"`n" +
"            # P13: should I relay?`n" +
"            try:`n" +
"                if packet.should_relay(self.node_id):`n" +
"                    logger.info('[Relay] relay request %s (hop %d/%d)',`n" +
"                                packet.packet_id[:16],`n" +
"                                packet.hop_count,`n" +
"                                packet.max_hops)`n" +
"                    packet.add_hop(self.node_id)`n" +
"                    packet.mark_relayed(self.node_id)`n" +
"                    self._forward_packet(packet, packet.route_to)`n" +
"                    return True, None`n" +
"            except Exception as _re:`n" +
"                logger.debug('[Relay] receive check error: %s', _re)`n"
                    
                    $orch = $orch.Substring(0, $lineEnd) + $relayCode + $orch.Substring($lineEnd)
                    Write-Host "[OK] receive() patched at: $parseIdx" -ForegroundColor Green
                } else {
                    Write-Host "[!!] indent check failed for receive" -ForegroundColor Red
                    Write-Host "    Next 30 chars: $after" -ForegroundColor Gray
                }
            }
        } else {
            Write-Host "[!!] packet = self._parse_packet not found in receive()" -ForegroundColor Red
        }
    }
}

# === 3. Save + check syntax (fixed) ===
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($orchPath, $orch, $utf8)
Write-Host "[OK] saved" -ForegroundColor Green

Write-Host ""
Write-Host "Checking syntax..." -ForegroundColor Cyan

$syntax = & python -c "import ast; ast.parse(open(r'$orchPath', encoding='utf-8').read()); print('OK')" 2>&1 | Out-String
Write-Host "Result: $syntax"

if ($syntax -notmatch "OK") {
    Write-Host "[!!] Syntax broken, restoring backup" -ForegroundColor Red
    Copy-Item (Join-Path $backupDir "orchestrator.py") $orchPath -Force
    Write-Host "[OK] restored from backup" -ForegroundColor Green
    exit 1
}

Write-Host ""
Write-Host "=== PATCH 13a-fix4-v2 DONE ===" -ForegroundColor Cyan
Write-Host "Restart: python -m web.app" -ForegroundColor Cyan