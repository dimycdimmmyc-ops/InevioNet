# Patch 7a: crypto signature verification
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"

# === 1. Проверим что в core/packet.py есть sign/verify ===
$packetPath = Join-Path $ProjectRoot "inevionet\core\packet.py"
$packet = [System.IO.File]::ReadAllText($packetPath, [System.Text.Encoding]::UTF8)

if ($packet.Contains("def verify")) {
    Write-Host "[--] packet.py already has verify()" -ForegroundColor Yellow
} else {
    Write-Host "[!!] packet.py needs verify() method" -ForegroundColor Yellow
    Write-Host "     Check manually: $packetPath" -ForegroundColor Gray
}

# === 2. Патчим orchestrator.py::receive() ===
$orchPath = Join-Path $ProjectRoot "inevionet\orchestrator.py"
$backupDir = Join-Path $ProjectRoot "_backup_crypto"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item $orchPath (Join-Path $backupDir "orchestrator.py") -Force
Write-Host "Backup: $backupDir\orchestrator.py"

$orch = [System.IO.File]::ReadAllText($orchPath, [System.Text.Encoding]::UTF8)
$orch = $orch -replace "`r`n", "`n"
$orch = $orch -replace "`r", "`n"

if ($orch.Contains("P13: verify signature")) {
    Write-Host "[!!] receive() already patched" -ForegroundColor Yellow
    return
}

$oldReceive = @'
    def receive(self, packet_data):
        try:
            packet = self._parse_packet(packet_data)
            if not packet: return False, None
            payload = packet.payload
            if getattr(packet, "_is_encrypted", False):
'@

$newReceive = @'
    def receive(self, packet_data):
        try:
            packet = self._parse_packet(packet_data)
            if not packet: return False, None

            # P13: verify signature
            sig_ok = True
            try:
                if hasattr(packet, "signature") and packet.signature:
                    sender_id = getattr(packet, "sender", "")
                    if sender_id and sender_id != self.node_id:
                        # Ищем публичный ключ отправителя
                        pub_key = None
                        if self._registry:
                            try:
                                rec = self._registry.get_device(sender_id)
                                if rec and hasattr(rec, "public_key"):
                                    pub_key = rec.public_key
                            except Exception:
                                pass
                        if pub_key:
                            sig_ok = packet.verify(pub_key)
                        else:
                            logger.debug("[Crypto] no pubkey for %s, skip verify", sender_id)
                if not sig_ok:
                    logger.warning("[Crypto] signature INVALID for packet %s from %s",
                                   getattr(packet, "packet_id", "?")[:16],
                                   getattr(packet, "sender", "?"))
                    return False, None
            except Exception as e:
                logger.debug("[Crypto] verify error: %s", e)

            payload = packet.payload
            if getattr(packet, "_is_encrypted", False):
'@

if ($orch.Contains($oldReceive)) {
    $orch = $orch.Replace($oldReceive, $newReceive)
    Write-Host "[OK] receive() patched with signature verify" -ForegroundColor Green
} else {
    Write-Host "[!!] receive() pattern not found - trying alternative" -ForegroundColor Yellow
    
    $altMarker = "            payload = packet.payload`n            if getattr(packet, `"_is_encrypted`", False):"
    $altNew = @'
            # P13: verify signature
            try:
                if hasattr(packet, "signature") and packet.signature:
                    sender_id = getattr(packet, "sender", "")
                    pub_key = None
                    if self._registry and sender_id:
                        try:
                            rec = self._registry.get_device(sender_id)
                            if rec and hasattr(rec, "public_key"):
                                pub_key = rec.public_key
                        except Exception:
                            pass
                    if pub_key:
                        if not packet.verify(pub_key):
                            logger.warning("[Crypto] INVALID signature from %s", sender_id)
                            return False, None
            except Exception as e:
                logger.debug("[Crypto] verify error: %s", e)

            payload = packet.payload
            if getattr(packet, "_is_encrypted", False):
'@
    
    if ($orch.Contains($altMarker)) {
        $orch = $orch.Replace($altMarker, $altNew)
        Write-Host "[OK] receive() patched (alt)" -ForegroundColor Green
    } else {
        Write-Host "[!!] Cannot find receive() body" -ForegroundColor Red
        return
    }
}

$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($orchPath, $orch, $utf8)
Write-Host "[OK] orchestrator.py saved" -ForegroundColor Green

# Проверка синтаксиса
python -c "import ast; ast.parse(open(r'$orchPath', encoding='utf-8').read()); print('OK')"