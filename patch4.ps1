# Patch 4: orchestrator.py - auto-stealth + fallback + scan_industrial
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"
$BackupDir = Join-Path $ProjectRoot "_backup_orchestrator"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

$path = Join-Path $ProjectRoot "inevionet\orchestrator.py"
Copy-Item $path (Join-Path $BackupDir "orchestrator.py") -Force
Write-Host "Backup: $BackupDir\orchestrator.py"

$content = [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)
$content = $content -replace "`r`n", "`n"
$content = $content -replace "`r", "`n"

# === 4.1. Модифицировать send() ===
if ($content.Contains("best_genome.use_stego")) {
    Write-Host "[!!] send() already patched" -ForegroundColor Yellow
} else {
    $oldSend = @'
    def send(self, receiver, payload, protocol=None, priority=5,
             use_stealth=False, stealth_method="HTTP_HEADERS", metadata=None):
        try:
            data_bytes = self._prepare_payload(payload)
            encrypted = self.crypto.encrypt(data_bytes)
            if protocol is None or protocol.lower() == "auto":
                protocol = self.selector.select() or "HTTPS"
            packet = create_packet(
                sender=self.node_id, receiver=receiver,
                payload=encrypted, protocol=protocol,
                priority=priority, metadata=metadata or {})
            packet._is_encrypted = True
            packet.sign(self.crypto.get_signing_keypair().private_key)
            target = self._resolve_target(receiver)
            success = False
            if use_stealth:
                result = self.stealth.send(
                    data=packet.to_bytes(), method=stealth_method)
                success = result.success
            else:
                result = self.transport.send(
                    data=packet.to_bytes(),
                    protocol=self._map_protocol(protocol),
                    target=target)
                success = result.success
'@

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
'@

    if ($content.Contains($oldSend)) {
        $content = $content.Replace($oldSend, $newSend)
        Write-Host "[OK] send() patched" -ForegroundColor Green
    } else {
        Write-Host "[!!] send() pattern not found - trying alternative" -ForegroundColor Yellow

        # Альтернативный поиск - более короткий кусок
        $altOld = "             use_stealth=False, stealth_method=`"HTTP_HEADERS`", metadata=None):"
        $altNew = "             use_stealth=None, stealth_method=None, metadata=None):"
        if ($content.Contains($altOld)) {
            $content = $content.Replace($altOld, $altNew)
            Write-Host "[OK] signature patched" -ForegroundColor Green
        }
    }
}

# === 4.2. Добавить scan_industrial перед get_discovered_nodes ===
if ($content.Contains("_scan_industrial_impl")) {
    Write-Host "[!!] scan_industrial already added" -ForegroundColor Yellow
} else {
    $oldMarker = "InevioNet.get_discovered_nodes = get_discovered_nodes"
    $newCode = @'
def _scan_industrial_impl(self, target, timeout=3.0):
    """P13: СЃРєР°РЅРёСЂРѕРІР°РЅРёРµ РїСЂРѕРјС‹С€Р»РµРЅРЅС‹С… РїСЂРѕС‚РѕРєРѕР»РѕРІ."""
    results = {}
    host = target.split(":")[0]

    # Modbus
    try:
        from .industrial.modbus import ModbusTCP
        mb = ModbusTCP(target_host=host, target_port=502, timeout=timeout)
        regs = mb.read_holding_registers(slave=1, address=0, count=4)
        results["modbus"] = {
            "found": bool(regs),
            "registers": regs or [],
        }
    except Exception as e:
        results["modbus"] = {"found": False, "error": str(e)}

    # MQTT
    try:
        from .industrial.mqtt import MQTTClient, PAHO_AVAILABLE
        if PAHO_AVAILABLE:
            mc = MQTTClient(target_host=host, target_port=1883, timeout=timeout)
            ok = mc.connect()
            mc.disconnect()
            results["mqtt"] = {"found": ok}
        else:
            results["mqtt"] = {"found": False, "error": "paho-mqtt not installed"}
    except Exception as e:
        results["mqtt"] = {"found": False, "error": str(e)}

    # OPC-UA
    try:
        from .industrial.opcua import OPCUA
        oc = OPCUA(endpoint=f"opc.tcp://{host}:4840", timeout=timeout)
        results["opcua"] = {"found": True, "note": "packet built"}
    except Exception as e:
        results["opcua"] = {"found": False, "error": str(e)}

    # DNP3
    try:
        from .industrial.dnp3 import DNP3
        d = DNP3(target_host=host, target_port=20000, timeout=timeout)
        pkt = d.wrap_for_inevionet(0x01, destination=1, address=0, count=1)
        results["dnp3"] = {"found": bool(pkt), "packet_size": len(pkt.data)}
        d.close()
    except Exception as e:
        results["dnp3"] = {"found": False, "error": str(e)}

    return results


InevioNet.scan_industrial = _scan_industrial_impl
InevioNet.get_discovered_nodes = get_discovered_nodes
'@

    if ($content.Contains($oldMarker)) {
        $content = $content.Replace($oldMarker, $newCode)
        Write-Host "[OK] scan_industrial() added" -ForegroundColor Green
    } else {
        Write-Host "[!!] marker not found - appending at end" -ForegroundColor Yellow
        $content = $content + "`n`n" + $newCode
        Write-Host "[OK] appended at end" -ForegroundColor Green
    }
}

# Сохраняем
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($path, $content, $utf8)
Write-Host "[OK] orchestrator.py saved" -ForegroundColor Green

# Проверка синтаксиса
python -c "import ast; ast.parse(open(r'$path', encoding='utf-8').read()); print('OK')"