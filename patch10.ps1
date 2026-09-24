# Patch 10: I2P transport via SAM bridge
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"

# === 1. Создать i2p_transport.py ===
$i2pPath = Join-Path $ProjectRoot "inevionet\network\i2p_transport.py"

if (Test-Path $i2pPath) {
    Write-Host "[--] i2p_transport.py already exists" -ForegroundColor Yellow
} else {
    $i2pCode = @'
"""P13: I2P transport via SAM Bridge (127.0.0.1:7656)."""
import socket
import struct
import time
import threading
from typing import Optional, Tuple
from ..core.logger import get_logger

logger = get_logger("inevionet.network.i2p_transport")


class I2PTransport:
    """P13: Маршрутизация через I2P SAM bridge.

    SAM (Simple Anonymous Messaging) - TCP протокол на 127.0.0.1:7656.
    I2P router его открывает автоматически при запуске.
    """

    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 7656
    DEFAULT_TIMEOUT = 30.0

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT,
                 timeout=DEFAULT_TIMEOUT, session_name="inevionet"):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.session_name = session_name
        self._available = None
        self._session_id = None

    def is_available(self) -> bool:
        """Проверить, запущен ли I2P router с SAM bridge."""
        if self._available is not None:
            return self._available
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3.0)
            s.connect((self.host, self.port))
            # Отправляем SAM HELLO
            s.sendall(b"HELLO VERSION MIN=3.0 MAX=3.3\n")
            resp = s.recv(4096).decode("utf-8", errors="replace")
            s.close()
            if "HELLO REPLY RESULT=OK" in resp:
                self._available = True
                logger.info("[I2P] SAM available at %s:%d", self.host, self.port)
            else:
                self._available = False
                logger.debug("[I2P] SAM HELLO failed: %s", resp[:100])
        except Exception as e:
            self._available = False
            logger.debug("[I2P] SAM unavailable: %s", e)
        return self._available

    def _create_session(self):
        """Создать SAM STREAM session."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        s.connect((self.host, self.port))

        # HELLO
        s.sendall(b"HELLO VERSION MIN=3.0 MAX=3.3\n")
        resp = s.recv(4096).decode("utf-8", errors="replace")
        if "HELLO REPLY RESULT=OK" not in resp:
            raise Exception("SAM HELLO failed: " + resp[:100])

        # SESSION CREATE
        cmd = ("SESSION CREATE STYLE=STREAM ID=" + self.session_name +
               " DESTINATION=TRANSIENT\n")
        s.sendall(cmd.encode("utf-8"))
        resp = s.recv(4096).decode("utf-8", errors="replace")
        if "SESSION STATUS RESULT=OK" not in resp:
            raise Exception("SESSION CREATE failed: " + resp[:200])

        logger.info("[I2P] Session created: %s", self.session_name)
        return s

    def send(self, data: bytes, target_host: str, target_port: int = 80):
        """Отправить данные через I2P.

        target_host должен быть .i2p адресом или base64 destination.
        """
        if not self.is_available():
            return False, None
        try:
            s = self._create_session()

            # STREAM CONNECT
            cmd = ("STREAM CONNECT ID=" + self.session_name +
                   " DESTINATION=" + target_host +
                   " SILENT=false\n")
            s.sendall(cmd.encode("utf-8"))

            # Ждём STREAM STATUS
            time.sleep(0.5)
            s.settimeout(10.0)
            try:
                resp = s.recv(4096).decode("utf-8", errors="replace")
                if "STREAM STATUS RESULT=OK" not in resp:
                    logger.debug("[I2P] STREAM CONNECT failed: %s", resp[:200])
                    s.close()
                    return False, None
            except socket.timeout:
                pass

            # Отправляем данные
            s.sendall(data)
            time.sleep(0.3)

            # Получаем ответ
            s.settimeout(5.0)
            try:
                response = s.recv(8192)
            except socket.timeout:
                response = b""

            s.close()
            return True, response

        except Exception as e:
            logger.debug("[I2P] send error: %s", e)
            return False, None

    def get_stats(self):
        return {
            "available": self.is_available(),
            "host": self.host,
            "port": self.port,
            "session": self.session_name,
        }

    def __repr__(self):
        status = "OK" if self._available else "OFF"
        return "I2PTransport([" + status + "] " + self.host + ":" + str(self.port) + ")"


if __name__ == "__main__":
    print("Testing I2PTransport...")
    t = I2PTransport()
    print("Available:", t.is_available())
    if t.is_available():
        print("Sending test to i2p-projekt.i2p...")
        ok, resp = t.send(b"GET / HTTP/1.0\r\n\r\n", "i2p-projekt.i2p", 80)
        print("Send:", ok, "Response:", len(resp) if resp else 0)
    print("I2PTransport OK")
'@

    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($i2pPath, $i2pCode, $utf8)
    Write-Host "[OK] Created: i2p_transport.py" -ForegroundColor Green

    python -c "import ast; ast.parse(open(r'$i2pPath', encoding='utf-8').read()); print('OK')"
}

# === 2. Добавить API endpoints в web/app.py ===
$appPath = Join-Path $ProjectRoot "web\app.py"
$app = [System.IO.File]::ReadAllText($appPath, [System.Text.Encoding]::UTF8)
$app = $app -replace "`r`n", "`n"

if ($app.Contains("/api/i2p/status")) {
    Write-Host "[--] I2P endpoints already added" -ForegroundColor Yellow
} else {
    $newEndpoints = @'
@app.route('/api/i2p/status')
def api_i2p_status():
    """P13: I2P availability."""
    try:
        from inevionet.network.i2p_transport import I2PTransport
        t = I2PTransport()
        return jsonify({'success': True, 'available': t.is_available()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/i2p/send', methods=['POST'])
def api_i2p_send():
    """P13: Send via I2P."""
    d = request.json or {}
    host = d.get('host', 'i2p-projekt.i2p')
    port = int(d.get('port', 80))
    data = d.get('data', 'GET / HTTP/1.0\r\n\r\n')
    try:
        from inevionet.network.i2p_transport import I2PTransport
        t = I2PTransport()
        if not t.is_available():
            return jsonify({'success': False, 'error': 'i2p_unavailable'}), 503
        ok, resp = t.send(data.encode('utf-8'), host, port)
        return jsonify({
            'success': ok,
            'response_len': len(resp) if resp else 0,
            'via': 'i2p',
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


'@

    $marker = "# ================================================================`n# SOCKETIO"
    $pos = $app.IndexOf($marker)
    if ($pos -lt 0) {
        $marker = "@socketio.on('connect')"
        $pos = $app.IndexOf($marker)
    }
    if ($pos -gt 0) {
        $app = $app.Substring(0, $pos) + $newEndpoints + $app.Substring($pos)
        $utf8 = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($appPath, $app, $utf8)
        Write-Host "[OK] app.py: I2P endpoints added" -ForegroundColor Green
        python -c "import ast; ast.parse(open(r'$appPath', encoding='utf-8').read()); print('OK')"
    } else {
        Write-Host "[!!] SOCKETIO marker not found" -ForegroundColor Red
    }
}

# === 3. UI: заменить Network Scanners на Anonymity ===
$htmlPath = Join-Path $ProjectRoot "web\templates\index.html"
$html = [System.IO.File]::ReadAllText($htmlPath, [System.Text.Encoding]::UTF8)
$html = $html -replace "`r`n", "`n"

if ($html.Contains("btnI2PStatus")) {
    Write-Host "[--] UI already patched" -ForegroundColor Yellow
} else {
    $newCard = @'
<div class="card">
<h3>Anonymity</h3>
<button class="btn secondary" onclick="checkTor()">Check Tor</button>
<button class="btn secondary" onclick="checkI2P()">Check I2P</button>
<div style="margin-top:10px;font-size:.8em;color:var(--dim)">Scanners:</div>
<button class="btn small" onclick="scanBLE()">BLE</button>
<button class="btn small" onclick="scanLTE()">LTE</button>
<button class="btn small" onclick="scanIndustrial()">Industrial</button>
<div id="netScanResult"></div>
</div>

'@

    $logMarker = 'id="logContainer"'
    $logPos = $html.IndexOf($logMarker)
    if ($logPos -gt 0) {
        $backPos = $html.LastIndexOf('<div class="card">', $logPos)
        if ($backPos -gt 0) {
            $html = $html.Substring(0, $backPos) + $newCard + $html.Substring($backPos)
            Write-Host "[OK] UI card added" -ForegroundColor Green
        }
    }

    $newJS = @'
// P13: I2P
async function checkI2P() {
    addLog('Checking I2P...', 'info');
    try {
        const r = await fetch('/api/i2p/status');
        const d = await r.json();
        const el = document.getElementById('netScanResult');
        if (d.available) {
            el.textContent = 'I2P: AVAILABLE (SAM 127.0.0.1:7656)';
            addLog('I2P OK', 'success');
        } else {
            el.textContent = 'I2P: NOT AVAILABLE';
            addLog('I2P router not running', 'warn');
        }
    } catch (e) {
        addLog('I2P check: ' + e, 'error');
    }
}

'@

    $jsMarker = "checkAuth();"
    $jsPos = $html.IndexOf($jsMarker)
    if ($jsPos -gt 0) {
        $html = $html.Substring(0, $jsPos) + $newJS + $html.Substring($jsPos)
    }

    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($htmlPath, $html, $utf8)
    Write-Host "[OK] index.html updated" -ForegroundColor Green
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  TESTING I2P" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
python -c "from inevionet.network.i2p_transport import I2PTransport; t = I2PTransport(); print('I2P available:', t.is_available())"

Write-Host ""
Write-Host "Done!" -ForegroundColor Green