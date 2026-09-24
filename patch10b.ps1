# Patch 10b v3: I2P integration (ASCII only)
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"

$orchPath = Join-Path $ProjectRoot "inevionet\orchestrator.py"
$backupDir = Join-Path $ProjectRoot "_backup_i2p"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item $orchPath (Join-Path $backupDir "orchestrator.py") -Force
Write-Host "Backup: $backupDir\orchestrator.py"

$orch = [System.IO.File]::ReadAllText($orchPath, [System.Text.Encoding]::UTF8)
$orch = $orch -replace "`r`n", "`n"

if ($orch.Contains("self.i2p = I2PTransport")) {
    Write-Host "[--] already patched" -ForegroundColor Yellow
    return
}

# === 1. Add I2PTransport to __init__ ===
$oldInit = "        self.stealth = SteganographyEngine()"
$newInit = "        self.stealth = SteganographyEngine()`n" +
           "        # P13: I2P integration`n" +
           "        try:`n" +
           "            from .network.i2p_transport import I2PTransport`n" +
           "            self.i2p = I2PTransport()`n" +
           "        except Exception as _e:`n" +
           "            self.i2p = None`n" +
           "            logger.debug('[I2P] init skipped: %s', _e)"

if ($orch.Contains($oldInit)) {
    $orch = $orch.Replace($oldInit, $newInit)
    Write-Host "[OK] I2PTransport added to init" -ForegroundColor Green
}

# === 2. Add send_via_i2p method before send_text ===
$marker = "    def send_text(self, receiver, text, **kwargs):"
$method = "    def send_via_i2p(self, data, target='i2p-projekt.i2p'):`n" +
          "        # P13: I2P integration - send via SAM bridge`n" +
          "        if not getattr(self, 'i2p', None):`n" +
          "            return False, None`n" +
          "        try:`n" +
          "            if not self.i2p.is_available():`n" +
          "                return False, None`n" +
          "            host = target`n" +
          "            port = 80`n" +
          "            if ':' in target:`n" +
          "                parts = target.rsplit(':', 1)`n" +
          "                try:`n" +
          "                    host = parts[0]`n" +
          "                    port = int(parts[1])`n" +
          "                except ValueError:`n" +
          "                    pass`n" +
          "            ok, resp = self.i2p.send(data, host, port)`n" +
          "            if ok:`n" +
          "                logger.info('[I2P] delivered %dB to %s', len(data), target)`n" +
          "            return ok, resp`n" +
          "        except Exception as e:`n" +
          "            logger.debug('[I2P] send error: %s', e)`n" +
          "            return False, None`n`n" +
          "    def send_text(self, receiver, text, **kwargs):"

if ($orch.Contains($marker)) {
    $orch = $orch.Replace($marker, $method)
    Write-Host "[OK] send_via_i2p added" -ForegroundColor Green
}

# === 3. Add I2P to default_protocols ===
$oldProto = '"MQTT", "MODBUS", "DNP3", "OPCUA"]'
$newProto = '"MQTT", "MODBUS", "DNP3", "OPCUA", "I2P"]'
if ($orch.Contains($oldProto)) {
    $orch = $orch.Replace($oldProto, $newProto)
    Write-Host "[OK] I2P added to protocols" -ForegroundColor Green
}

# === 4. Add I2P to stats ===
$oldStats = '            "selector": self.selector.get_stats(),'
$newStats = "            `"selector`": self.selector.get_stats(),`n" +
           "            `"i2p`": self.i2p.get_stats() if getattr(self, 'i2p', None) else {'available': False},"
if ($orch.Contains($oldStats)) {
    $orch = $orch.Replace($oldStats, $newStats)
    Write-Host "[OK] I2P stats added" -ForegroundColor Green
}

# === 5. Add I2P hook to try_delivery via simple string ===
$oldTry = "        def try_delivery(alt, depth):" + "`n" + "            proto = alt[`"protocol`"]"
$newTry = "        def try_delivery(alt, depth):" + "`n" +
          "            proto = alt[`"protocol`"]" + "`n" +
          "            if proto == 'I2P':" + "`n" +
          "                ok, resp = self.send_via_i2p(packet.to_bytes(), target if target else 'i2p-projekt.i2p')" + "`n" +
          "                if ok:" + "`n" +
          "                    if self.evolution:" + "`n" +
          "                        self.evolution.reward('protocol', 'I2P', True)" + "`n" +
          "                    return True, 0.95" + "`n" +
          "                return False, 0.3"

if ($orch.Contains($oldTry)) {
    $orch = $orch.Replace($oldTry, $newTry)
    Write-Host "[OK] I2P added to try_delivery" -ForegroundColor Green
}

$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($orchPath, $orch, $utf8)
Write-Host "[OK] orchestrator.py saved" -ForegroundColor Green

python -c "import ast; ast.parse(open(r'$orchPath', encoding='utf-8').read()); print('OK')"