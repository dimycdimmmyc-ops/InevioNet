# Patch 11a: WebRTC Bridge module
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"

# === 1. Установить aiortc ===
Write-Host "[1/2] Installing aiortc..." -ForegroundColor Cyan
pip install aiortc --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] aiortc installed" -ForegroundColor Green
} else {
    Write-Host "[!!] aiortc install failed - try manually" -ForegroundColor Red
}

# === 2. Создать webrtc_bridge.py ===
$bridgePath = Join-Path $ProjectRoot "inevionet\network\webrtc_bridge.py"

if (Test-Path $bridgePath) {
    Write-Host "[--] webrtc_bridge.py already exists" -ForegroundColor Yellow
} else {
    $bridgeCode = @'
"""P13: WebRTC Bridge - Snowflake-like P2P proxy."""
import asyncio
import json
import time
from typing import Optional, Callable
from ..core.logger import get_logger

logger = get_logger("inevionet.network.webrtc_bridge")

try:
    from aiortc import RTCPeerConnection, RTCSessionDescription
    AIORTC_AVAILABLE = True
except ImportError:
    AIORTC_AVAILABLE = False
    logger.warning("[WebRTC] aiortc not installed")


class WebRTCBridge:
    """P13: WebRTC DataChannel for P2P proxying."""

    def __init__(self, node_id="local"):
        self.node_id = node_id
        self.peer_id = None
        self.pc = None
        self.data_channel = None
        self._connected = False
        self._message_handlers = []
        self._stats = {
            "connections": 0, "bytes_sent": 0, "bytes_received": 0,
            "messages_sent": 0, "messages_received": 0, "errors": 0,
        }

    def is_available(self):
        return AIORTC_AVAILABLE

    async def create_offer(self):
        """Client creates WebRTC offer."""
        if not AIORTC_AVAILABLE:
            return None
        try:
            self.pc = RTCPeerConnection()
            self.data_channel = self.pc.createDataChannel("inevionet")
            self._setup_channel(self.data_channel)

            @self.pc.on("iceconnectionstatechange")
            async def on_ice_state():
                state = self.pc.iceConnectionState
                logger.info("[WebRTC] ICE: %s", state)
                if state == "connected":
                    self._connected = True
                    self._stats["connections"] += 1
                elif state in ("failed", "closed"):
                    self._connected = False

            offer = await self.pc.createOffer()
            await self.pc.setLocalDescription(offer)
            await self._wait_for_ice_gathering()

            offer_json = {
                "type": self.pc.localDescription.type,
                "sdp": self.pc.localDescription.sdp,
            }
            offer_str = json.dumps(offer_json)
            logger.info("[WebRTC] Offer created (%d bytes)", len(offer_str))
            return offer_str
        except Exception as e:
            logger.error("[WebRTC] create_offer error: %s", e)
            self._stats["errors"] += 1
            return None

    async def accept_offer(self, offer_str):
        """Proxy accepts offer, returns answer."""
        if not AIORTC_AVAILABLE:
            return None
        try:
            offer_json = json.loads(offer_str)
            self.pc = RTCPeerConnection()

            @self.pc.on("datachannel")
            def on_datachannel(channel):
                logger.info("[WebRTC] DataChannel: %s", channel.label)
                self.data_channel = channel
                self._setup_channel(channel)

            @self.pc.on("iceconnectionstatechange")
            async def on_ice_state():
                state = self.pc.iceConnectionState
                logger.info("[WebRTC] ICE: %s", state)
                if state == "connected":
                    self._connected = True
                    self._stats["connections"] += 1

            offer = RTCSessionDescription(
                sdp=offer_json["sdp"], type=offer_json["type"])
            await self.pc.setRemoteDescription(offer)
            answer = await self.pc.createAnswer()
            await self.pc.setLocalDescription(answer)
            await self._wait_for_ice_gathering()

            answer_json = {
                "type": self.pc.localDescription.type,
                "sdp": self.pc.localDescription.sdp,
            }
            answer_str = json.dumps(answer_json)
            logger.info("[WebRTC] Answer created (%d bytes)", len(answer_str))
            return answer_str
        except Exception as e:
            logger.error("[WebRTC] accept_offer error: %s", e)
            self._stats["errors"] += 1
            return None

    async def accept_answer(self, answer_str):
        """Client accepts answer."""
        if not AIORTC_AVAILABLE or not self.pc:
            return False
        try:
            answer_json = json.loads(answer_str)
            answer = RTCSessionDescription(
                sdp=answer_json["sdp"], type=answer_json["type"])
            await self.pc.setRemoteDescription(answer)
            logger.info("[WebRTC] Answer accepted")
            return True
        except Exception as e:
            logger.error("[WebRTC] accept_answer error: %s", e)
            return False

    def _setup_channel(self, channel):
        @channel.on("open")
        def on_open():
            logger.info("[WebRTC] DataChannel opened")
            self._connected = True

        @channel.on("close")
        def on_close():
            logger.info("[WebRTC] DataChannel closed")
            self._connected = False

        @channel.on("message")
        def on_message(message):
            self._stats["messages_received"] += 1
            self._stats["bytes_received"] += len(message) if message else 0
            for h in self._message_handlers:
                try:
                    h(message)
                except Exception as e:
                    logger.error("[WebRTC] handler: %s", e)

    async def _wait_for_ice_gathering(self, timeout=5.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.pc.iceGatheringState == "complete":
                return
            await asyncio.sleep(0.1)

    def send(self, data):
        if not self.data_channel or not self._connected:
            return False
        try:
            if isinstance(data, bytes):
                self.data_channel.send(data)
            else:
                self.data_channel.send(str(data))
            self._stats["messages_sent"] += 1
            self._stats["bytes_sent"] += len(data) if data else 0
            return True
        except Exception as e:
            logger.error("[WebRTC] send: %s", e)
            self._stats["errors"] += 1
            return False

    def on_message(self, handler):
        self._message_handlers.append(handler)

    async def close(self):
        if self.data_channel:
            try:
                self.data_channel.close()
            except Exception:
                pass
        if self.pc:
            try:
                await self.pc.close()
            except Exception:
                pass
        self._connected = False

    def get_stats(self):
        return {
            **self._stats,
            "available": AIORTC_AVAILABLE,
            "connected": self._connected,
            "peer_id": self.peer_id,
        }

    def __repr__(self):
        status = "OK" if self._connected else "IDLE"
        return "WebRTCBridge([" + status + "] " + self.node_id + ")"


if __name__ == "__main__":
    print("Testing WebRTCBridge...")
    b = WebRTCBridge("test")
    print("Available:", b.is_available())
    print("Stats:", b.get_stats())
    print("WebRTCBridge OK")
'@

    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($bridgePath, $bridgeCode, $utf8)
    Write-Host "[OK] Created: webrtc_bridge.py" -ForegroundColor Green

    python -c "import ast; ast.parse(open(r'$bridgePath', encoding='utf-8').read()); print('OK')"
}

# === 3. Тест ===
Write-Host ""
Write-Host "[2/2] Testing WebRTCBridge..." -ForegroundColor Cyan
python -c "from inevionet.network.webrtc_bridge import WebRTCBridge; b = WebRTCBridge('test'); print('Available:', b.is_available()); print('Stats:', b.get_stats())"