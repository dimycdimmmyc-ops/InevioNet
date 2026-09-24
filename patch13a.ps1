# Patch 13a: Connect hop-mechanism (real relays)
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"

$orchPath = Join-Path $ProjectRoot "inevionet\orchestrator.py"
$backupDir = Join-Path $ProjectRoot "_backup_relay"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item $orchPath (Join-Path $backupDir "orchestrator.py") -Force
Write-Host "Backup: $backupDir\orchestrator.py"

$orch = [System.IO.File]::ReadAllText($orchPath, [System.Text.Encoding]::UTF8)
$orch = $orch -replace "`r`n", "`n"

if ($orch.Contains("P13: hop-mechanism connected")) {
    Write-Host "[--] already patched" -ForegroundColor Yellow
    return
}

# === 1. Р”РѕР±Р°РІРёС‚СЊ relay РјРµС‚РѕРґС‹ РїРµСЂРµРґ send_text ===
$marker = "    def send_text(self, receiver, text, **kwargs):"
$newMethods = @'
    def _topology_loop(self):
        """P13: hop-mechanism connected - build topology periodically."""
        import time as _t
        while getattr(self, "_running", False):
            _t.sleep(30)
            if not getattr(self, "_running", False):
                break
            try:
                topo = self.enable_auto_topology()
                info = topo.build_from_scanner(min_quality=0.2)
                if info.get("success"):
                    stats = topo.get_stats()
                    logger.info("[Topology] nodes=%d edges=%d",
                                stats.get("node_count", 0),
                                stats.get("edge_count", 0))
            except Exception as e:
                logger.debug("[Topology] loop error: %s", e)

    def _forward_packet(self, packet, next_hop):
        """P13: hop-mechanism connected - forward relay packet."""
        try:
            target = self._resolve_target(next_hop)
            if not target:
                logger.warning("[Relay] no target for %s", next_hop)
                return False
            result = self.transport.send(
                data=packet.to_bytes(),
                protocol=self._map_protocol(packet.protocol or "HTTPS"),
                target=target)
            if result.success:
                logger.info("[Relay] Forwarded %s to %s (hop %d/%d)",
                            packet.packet_id[:16], next_hop,
                            packet.hop_count, packet.max_hops)
                return True
            return False
        except Exception as e:
            logger.error("[Relay] forward error: %s", e)
            return False

    def _try_relay_chain(self, packet, receiver):
        """P13: hop-mechanism connected - try to route via chain."""
        try:
            topo = self.enable_auto_topology()
            path = None
            if hasattr(topo, "shortest_path"):
                path = topo.shortest_path(self.node_id, receiver)
            if not path or len(path) < 2:
                return False, None
            next_hop = path[1] if len(path) > 1 else None
            if not next_hop or next_hop == receiver:
                return False, None
            packet.route_to = next_hop
            packet.max_hops = max(2, len(path) - 1)
            packet.origin = self.node_id
            packet.metadata["full_path"] = path
            logger.info("[Relay] Chain: %s", " -> ".join(path))
            target = self._resolve_target(next_hop)
            if not target:
                return False, None
            result = self.transport.send(
                data=packet.to_bytes(),
                protocol=self._map_protocol(packet.protocol or "HTTPS"),
                target=target)
            return result.success, path
        except Exception as e:
            logger.debug("[Relay] chain error: %s", e)
            return False, None

    def send_text(self, receiver, text, **kwargs):
'@

if ($orch.Contains($marker)) {
    $orch = $orch.Replace($marker, $newMethods)
    Write-Host "[OK] relay methods added" -ForegroundColor Green
}

# === 2. РњРѕРґРёС„РёС†РёСЂРѕРІР°С‚СЊ try_delivery РІ send_with_guarantee ===
$oldTry = @'
                # P13: I2P integration
                if proto == "I2P":
                    ok, resp = self.send_via_i2p(packet.to_bytes(), target if target else 'i2p-projekt.i2p')
                    if ok:
                        if self.evolution:
                            self.evolution.reward('protocol', 'I2P', True)
                        return True, 0.95
                    return False, 0.3
'@

$newTry = @'
                # P13: hop-mechanism connected - try relay chain first
                if proto not in ("I2P", "MQTT", "MODBUS", "DNP3", "OPCUA"):
                    chain_ok, chain_path = self._try_relay_chain(packet, receiver)
                    if chain_ok:
                        if self.evolution:
                            self.evolution.reward('protocol', proto, True)
                        return True, 0.95

                # P13: I2P integration
                if proto == "I2P":
                    ok, resp = self.send_via_i2p(packet.to_bytes(), target if target else 'i2p-projekt.i2p')
                    if ok:
                        if self.evolution:
                            self.evolution.reward('protocol', 'I2P', True)
                        return True, 0.95
                    return False, 0.3
'@

if ($orch.Contains($oldTry)) {
    $orch = $orch.Replace($oldTry, $newTry)
    Write-Host "[OK] try_delivery patched" -ForegroundColor Green
}

# === 3. РњРѕРґРёС„РёС†РёСЂРѕРІР°С‚СЊ receive() вЂ” РѕР±СЂР°Р±РѕС‚РєР° relay ===
$oldRecv = @'
    def receive(self, packet_data):
        try:
            packet = self._parse_packet(packet_data)
            if not packet: return False, None

            # P13: verify signature
'@

$newRecv = @'
    def receive(self, packet_data):
        try:
            packet = self._parse_packet(packet_data)
            if not packet: return False, None

            # P13: hop-mechanism connected - should I relay?
            try:
                if packet.should_relay(self.node_id):
                    logger.info("[Relay] Relay request %s (hop %d/%d) route_to=%s",
                                packet.packet_id[:16], packet.hop_count,
                                packet.max_hops, packet.route_to)
                    packet.add_hop(self.node_id)
                    packet.mark_relayed(self.node_id)
                    self._forward_packet(packet, packet.route_to)
                    return True, None
            except Exception as e:
                logger.debug("[Relay] receive relay error: %s", e)

            # P13: verify signature
'@

if ($orch.Contains($oldRecv)) {
    $orch = $orch.Replace($oldRecv, $newRecv)
    Write-Host "[OK] receive() patched" -ForegroundColor Green
}

# === 4. Р—Р°РїСѓСЃС‚РёС‚СЊ topology loop РїСЂРё start ===
$oldStart = @'
        logger.info(f"InevioNet started: {self.node_id}")
'@

$newStart = @'
        try:
            import threading as _th
            _th.Thread(target=self._topology_loop, daemon=True,
                       name="topology_loop").start()
            logger.info("[Relay] topology loop started")
        except Exception as e:
            logger.debug("[Relay] topology loop failed: %s", e)
        logger.info(f"InevioNet started: {self.node_id}")
'@

if ($orch.Contains($oldStart)) {
    $orch = $orch.Replace($oldStart, $newStart)
    Write-Host "[OK] topology loop hooked" -ForegroundColor Green
}

# === 5. Р”РѕР±Р°РІРёС‚СЊ С„Р»Р°Рі P13 ===
$orch = $orch.Replace(
    "logger = get_logger(""inevionet.orchestrator"")",
    "logger = get_logger(""inevionet.orchestrator"")`n# P13: hop-mechanism connected")

$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($orchPath, $orch, $utf8)
Write-Host "[OK] orchestrator.py saved" -ForegroundColor Green

python -c "import ast; ast.parse(open(r'$orchPath', encoding='utf-8').read()); print('OK')"

# === 6. Р”РѕР±Р°РІРёС‚СЊ /api/relay/incoming РІ web/app.py ===
$appPath = Join-Path $ProjectRoot "web\app.py"
$app = [System.IO.File]::ReadAllText($appPath, [System.Text.Encoding]::UTF8)
$app = $app -replace "`r`n", "`n"

if ($app.Contains("/api/relay/incoming")) {
    Write-Host "[--] relay/incoming already present" -ForegroundColor Yellow
} else {
    $newEndpoint = @'
@app.route('/api/relay/incoming', methods=['POST'])
def api_relay_incoming():
    """P13: receive relay packet and forward."""
    try:
        data = request.get_data()
        if not data:
            return jsonify({'success': False, 'error': 'empty'}), 400
        n = get_net()
        ok, result = n.receive(data)
        return jsonify({'success': bool(ok), 'packet_id': None})
    except Exception as e:
        log.error('[Relay] incoming error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


'@
    $marker = "@socketio.on('connect')"
    $pos = $app.IndexOf($marker)
    if ($pos -gt 0) {
        $app = $app.Substring(0, $pos) + $newEndpoint + $app.Substring($pos)
        $utf8 = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($appPath, $app, $utf8)
        Write-Host "[OK] /api/relay/incoming added" -ForegroundColor Green
        python -c "import ast; ast.parse(open(r'$appPath', encoding='utf-8').read()); print('OK')"
    }
}

Write-Host ""
Write-Host "=== PATCH 13a DONE ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Changes:" -ForegroundColor Yellow
Write-Host "  [OK] _topology_loop() - topology every 30s" -ForegroundColor White
Write-Host "  [OK] _forward_packet() - relay forwarding" -ForegroundColor White
Write-Host "  [OK] _try_relay_chain() - chain routing" -ForegroundColor White
Write-Host "  [OK] send_with_guarantee: tries chain first" -ForegroundColor White
Write-Host "  [OK] receive: handles should_relay()" -ForegroundColor White
Write-Host "  [OK] /api/relay/incoming endpoint" -ForegroundColor White
Write-Host ""
Write-Host "Restart: python -m web.app" -ForegroundColor Cyan