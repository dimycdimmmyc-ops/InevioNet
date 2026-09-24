# Patch 13a-fix4: connect try_delivery + receive to relay
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"
$orchPath = Join-Path $ProjectRoot "inevionet\orchestrator.py"

# Backup
$backupDir = Join-Path $ProjectRoot "_backup_relay_v4"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item $orchPath (Join-Path $backupDir "orchestrator.py") -Force
Write-Host "Backup: $backupDir\orchestrator.py" -ForegroundColor Cyan

$orch = [System.IO.File]::ReadAllText($orchPath, [System.Text.Encoding]::UTF8)
$orch = $orch -replace "`r`n", "`n"

# === 1. РџР°С‚С‡ try_delivery ===
if ($orch.Contains("# P13: try relay chain first")) {
    Write-Host "[--] try_delivery already patched" -ForegroundColor Yellow
} else {
    # РќР°Р№С‚Рё try_delivery
    $tryStart = $orch.IndexOf("        def try_delivery(alt, depth):")
    if ($tryStart -lt 0) {
        Write-Host "[!!] try_delivery NOT found" -ForegroundColor Red
    } else {
        Write-Host "try_delivery at: $tryStart" -ForegroundColor Cyan
        
        # РќР°Р№С‚Рё "proto = alt" Рё РµРіРѕ РєРѕРЅРµС†
        $protoIdx = $orch.IndexOf("            proto = alt[", $tryStart)
        if ($protoIdx -ge 0) {
            $lineEnd = $orch.IndexOf("`n", $protoIdx)
            if ($lineEnd -gt 0) {
                # Р’СЃС‚Р°РІРёС‚СЊ chain-try СЃ РїСЂР°РІРёР»СЊРЅС‹Рј РѕС‚СЃС‚СѓРїРѕРј (16 РїСЂРѕР±РµР»РѕРІ)
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
            }
        }
    }
}

# === 2. РџР°С‚С‡ receive() ===
if ($orch.Contains("# P13: should I relay")) {
    Write-Host "[--] receive() already patched" -ForegroundColor Yellow
} else {
    $recvStart = $orch.IndexOf("    def receive(self, packet_data):")
    if ($recvStart -lt 0) {
        Write-Host "[!!] receive() NOT found" -ForegroundColor Red
    } else {
        Write-Host "receive() at: $recvStart" -ForegroundColor Cyan
        
        # РќР°Р№С‚Рё "packet = self._parse_packet" Рё РµРіРѕ РєРѕРЅРµС†
        $parseIdx = $orch.IndexOf("packet = self._parse_packet(packet_data)", $recvStart)
        if ($parseIdx -ge 0) {
            $lineEnd = $orch.IndexOf("`n", $parseIdx)
            if ($lineEnd -gt 0) {
                # Р’СЃС‚Р°РІРёС‚СЊ relay-check СЃ РїСЂР°РІРёР»СЊРЅС‹Рј РѕС‚СЃС‚СѓРїРѕРј (12 РїСЂРѕР±РµР»РѕРІ)
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
                Write-Host "[OK] receive() patched" -ForegroundColor Green
            }
        }
    }
}

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
Write-Host "=== PATCH 13a-fix4 DONE ===" -ForegroundColor Cyan
Write-Host "Restart: python -m web.app" -ForegroundColor Cyan