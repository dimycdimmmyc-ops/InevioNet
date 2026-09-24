# Patch 4b: orchestrator.py - replace send() body safely
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"

$path = Join-Path $ProjectRoot "inevionet\orchestrator.py"
$content = [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)
$content = $content -replace "`r`n", "`n"
$content = $content -replace "`r", "`n"

# Проверка - уже патчено?
if ($content.Contains("best_genome = self.evolution.get_best_genome()")) {
    Write-Host "[!!] send() already patched with auto-stealth" -ForegroundColor Yellow
    return
}

# Найдём позиции методов
$startMarker = "    def send(self, receiver, payload, protocol=None, priority=5,"
$endMarker = "    def send_with_guarantee(self, receiver, payload"

$startPos = $content.IndexOf($startMarker)
$endPos = $content.IndexOf($endMarker)

if ($startPos -lt 0) {
    Write-Host "[!!] def send() not found" -ForegroundColor Red
    return
}
if ($endPos -lt 0) {
    Write-Host "[!!] def send_with_guarantee() not found" -ForegroundColor Red
    return
}

Write-Host "send() start: $startPos" -ForegroundColor Cyan
Write-Host "send_with_guarantee() start: $endPos" -ForegroundColor Cyan

# Новое тело send()
$newSend = @'
    def send(self, receiver, payload, protocol=None, priority=5,
             use_stealth=None, stealth_method=None, metadata=None):
        try:
            data_bytes = self._prepare_payload(payload)
            encrypted = self.crypto.encrypt(data_bytes)
            if protocol is None or protocol.lower() == "auto":
                protocol = self.selector.select() or "HTTPS"

            # P13: auto-select strategies from best genome
            best_genome = self.evolution.get_best_genome() if self.evolution else None
            if use_stealth is None:
                use_stealth = best_genome.use_stego if best_genome else False
            if stealth_method is None:
                stealth_method = best_genome.stego_method if best_genome else "HTTP_HEADERS"

            packet = create_packet(
                sender=self.node_id, receiver=receiver,
                payload=encrypted, protocol=protocol,
                priority=priority, metadata=metadata or {})
            packet._is_encrypted = True
            packet.sign(self.crypto.get_signing_keypair().private_key)
            target = self._resolve_target(receiver)
            success = False
            used_method = None
            if use_stealth:
                result = self.stealth.send(
                    data=packet.to_bytes(), method=stealth_method, target=target)
                success = result.success
                used_method = ("stego", stealth_method)
            else:
                result = self.transport.send(
                    data=packet.to_bytes(),
                    protocol=self._map_protocol(protocol),
                    target=target)
                success = result.success
                used_method = ("protocol", protocol)

                # P13: fallback to steganography
                if not success:
                    logger.info("[Stealth] fallback to steganography")
                    stego_result = self.stealth.send_auto(
                        data=packet.to_bytes(),
                        target=target,
                        priorities=["HTTP_HEADERS", "DNS_QNAME", "ICMP_PAYLOAD"])
                    if stego_result.success:
                        success = True
                        used_method = ("stego", stego_result.method)
                        logger.info("[Stealth] delivered via %s", stego_result.method)

            # P13: reward for evolution
            if self.evolution and used_method:
                s_type, s_val = used_method
                self.evolution.reward(s_type, s_val, success)

            with self._lock:
                self.stats["packets_sent"] += 1
                self.stats["bytes_sent"] += len(data_bytes)
                if success:
                    self.stats["packets_delivered"] += 1
                    self.selector.record_success(protocol)
                else:
                    self.stats["packets_failed"] += 1
                    self.selector.record_failure(protocol)
                self.sent_packets[packet.packet_id] = packet
            self._trigger_event("on_send", packet)
            if success:
                self._trigger_event("on_delivery", packet)
            return packet
        except Exception as e:
            logger.error(f"Send error: {e}")
            self._trigger_event("on_error", {"error": str(e)})
            return None

'@

# Собираем новый контент
$newContent = $content.Substring(0, $startPos) + $newSend + $content.Substring($endPos)

# Сохраняем
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($path, $newContent, $utf8)
Write-Host "[OK] orchestrator.py patched" -ForegroundColor Green

# Проверка синтаксиса
$check = python -c "import ast; ast.parse(open(r'$path', encoding='utf-8').read()); print('OK')" 2>&1
Write-Host "Syntax: $check"