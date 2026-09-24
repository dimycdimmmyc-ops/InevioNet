# Patch 13a-fix: connect chain + relay precisely
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"
$orchPath = Join-Path $ProjectRoot "inevionet\orchestrator.py"

$orch = [System.IO.File]::ReadAllText($orchPath, [System.Text.Encoding]::UTF8)
$orch = $orch -replace "`r`n", "`n"

# === 1. РџР°С‚С‡ try_delivery С‡РµСЂРµР· IndexOf ===
if ($orch.Contains("chain_ok, chain_path")) {
    Write-Host "[--] try_delivery already patched" -ForegroundColor Yellow
} else {
    # РќР°Р№С‚Рё С„СѓРЅРєС†РёСЋ try_delivery
    $tryStart = $orch.IndexOf("        def try_delivery(alt, depth):")
    if ($tryStart -lt 0) {
        Write-Host "[!!] try_delivery not found" -ForegroundColor Red
    } else {
        Write-Host "try_delivery at: $tryStart" -ForegroundColor Cyan
        
        # РќР°Р№С‚Рё РїРµСЂРІСѓСЋ СЃС‚СЂРѕРєСѓ С‚РµР»Р° С„СѓРЅРєС†РёРё - РїРѕСЃР»Рµ "proto = alt[...]"
        $protoLine = $orch.IndexOf("            proto = alt[", $tryStart)
        if ($protoLine -lt 0) {
            Write-Host "[!!] proto line not found" -ForegroundColor Red
        } else {
            # РќР°Р№С‚Рё РєРѕРЅРµС† СЃС‚СЂРѕРєРё СЃ proto = alt[...]
            $protoEnd = $orch.IndexOf("`n", $protoLine)
            if ($protoEnd -lt 0) { $protoEnd = $protoLine + 40 }
            
            # Р’СЃС‚Р°РІРёС‚СЊ chain-try СЃСЂР°Р·Сѓ РїРѕСЃР»Рµ proto = ...
            $chainTry = "`n" +
"                # P13: try relay chain FIRST`n" +
"                if proto not in ('I2P', 'MQTT', 'MODBUS', 'DNP3', 'OPCUA'):`n" +
"                    try:`n" +
"                        chain_ok, chain_path = self._try_relay_chain(packet, receiver)`n" +
"                        if chain_ok:`n" +
"                            if self.evolution:`n" +
"                                self.evolution.reward('protocol', proto, True)`n" +
"                            return True, 0.95`n" +
"                    except Exception as _e:`n" +
"                        logger.debug('[Relay] chain try error: %s', _e)`n"
            
            $orch = $orch.Substring(0, $protoEnd) + $chainTry + $orch.Substring($protoEnd)
            Write-Host "[OK] try_delivery patched (chain first)" -ForegroundColor Green
        }
    }
}

# === 2. РџР°С‚С‡ receive() С‡РµСЂРµР· IndexOf ===
if ($orch.Contains("# P13: hop-mechanism - should I relay")) {
    Write-Host "[--] receive() already patched" -ForegroundColor Yellow
} else {
    $recvStart = $orch.IndexOf("    def receive(self, packet_data):")
    if ($recvStart -lt 0) {
        Write-Host "[!!] receive() not found" -ForegroundColor Red
    } else {
        Write-Host "receive() at: $recvStart" -ForegroundColor Cyan
        
        # РќР°Р№С‚Рё "packet = self._parse_packet(packet_data)"
        $parseLine = $orch.IndexOf("packet = self._parse_packet(packet_data)", $recvStart)
        if ($parseLine -lt 0) {
            Write-Host "[!!] parse_packet line not found" -ForegroundColor Red
        } else {
            # РќР°Р№С‚Рё РєРѕРЅРµС† СЌС‚РѕР№ СЃС‚СЂРѕРєРё
            $parseEnd = $orch.IndexOf("`n", $parseLine)
            if ($parseEnd -lt 0) { $parseEnd = $parseLine + 60 }
            
            # Р’СЃС‚Р°РІРёС‚СЊ relay-РїСЂРѕРІРµСЂРєСѓ РїРѕСЃР»Рµ РїР°СЂСЃРёРЅРіР°
            $relayCheck = "`n" +
"`n" +
"            # P13: hop-mechanism - should I relay?`n" +
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
"            except Exception as _e:`n" +
"                logger.debug('[Relay] receive check error: %s', _e)`n"
            
            $orch = $orch.Substring(0, $parseEnd) + $relayCheck + $orch.Substring($parseEnd)
            Write-Host "[OK] receive() patched (relay check)" -ForegroundColor Green
        }
    }
}

# РЎРѕС…СЂР°РЅРёС‚СЊ
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($orchPath, $orch, $utf8)
Write-Host "[OK] orchestrator.py saved" -ForegroundColor Green

python -c "import ast; ast.parse(open(r'$orchPath', encoding='utf-8').read()); print('OK')"

Write-Host ""
Write-Host "=== PATCH 13a-fix DONE ===" -ForegroundColor Cyan
Write-Host "Restart: python -m web.app" -ForegroundColor Cyan