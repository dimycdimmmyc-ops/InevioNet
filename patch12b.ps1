# Patch 12b: Cellular networks scanner
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"

# ============================================================
# 1. Create cellular_scanner.py
# ============================================================
$cellPath = Join-Path $ProjectRoot "inevionet\network\cellular_scanner.py"

if (Test-Path $cellPath) {
    Write-Host "[--] cellular_scanner.py already exists" -ForegroundColor Yellow
} else {
    $cellCode = @'
"""P13: Cellular scanner - LTE/5G/GSM detection + operator lookup."""
import re
import sys
import json
import socket
import subprocess
import urllib.request
from typing import List, Dict, Any, Optional
from ..core.logger import get_logger

logger = get_logger("inevionet.network.cellular_scanner")


# MCC/MNC -> operator name (RU + CIS)
OPERATORS = {
    "25001": "MTS", "25002": "MegaFon", "25020": "Tele2",
    "25099": "Beeline", "25011": "Yota", "25016": "MTS",
    "25017": "MTS", "25035": "MOTIV", "25039": "Rostelecom",
    "25050": "MTS", "25092": "MegaFon",
    "25501": "Vodafone UA", "25502": "Kyivstar", "25503": "lifecell",
    "25701": "A1 BY", "25702": "MTS BY", "25704": "life:)",
    "40101": "Beeline KZ", "40102": "Kcell", "40177": "Tele2 KZ",
}


def scan_cellular() -> List[Dict[str, Any]]:
    """Scan for cellular networks.

    Uses netsh mbn (Windows) or mmcli (Linux). If no modem,
    returns empty list.
    """
    if sys.platform == "win32":
        return _scan_cellular_windows()
    return _scan_cellular_linux()


def _scan_cellular_windows() -> List[Dict[str, Any]]:
    """Windows: netsh mbn show interfaces."""
    results = []
    try:
        r = subprocess.run(
            ["netsh", "mbn", "show", "interfaces"],
            capture_output=True, timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            raw = r.stdout.decode("cp866", errors="replace")
        except Exception:
            raw = r.stdout.decode("utf-8", errors="replace")

        current = {}
        for line in raw.splitlines():
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            key_l = key.strip().lower()
            val = val.strip()

            if "имя оператора" in key_l or "operator" in key_l:
                current["operator"] = val
            elif "технология" in key_l or "technology" in key_l:
                current["tech"] = val
            elif "уровень сигнала" in key_l or "signal" in key_l:
                current["signal"] = val
            elif "идентификатор" in key_l or "id" in key_l:
                current["cell_id"] = val
            elif not line.startswith(" ") and current:
                results.append(current)
                current = {}

        if current:
            results.append(current)

        for c in results:
            c["type"] = "5g" if "5g" in c.get("tech", "").lower() else "lte"
            c["operator"] = c.get("operator", "unknown")

    except Exception as e:
        logger.debug("[Cellular] netsh mbn error: %s", e)
    return results


def _scan_cellular_linux() -> List[Dict[str, Any]]:
    """Linux: mmcli -L."""
    results = []
    try:
        r = subprocess.run(["mmcli", "-L"], capture_output=True, timeout=5)
        raw = r.stdout.decode("utf-8", errors="replace")
        for line in raw.splitlines():
            m = re.match(r"\s*/Modem/(\d+)", line)
            if m:
                results.append({
                    "modem_id": m.group(1),
                    "operator": "unknown",
                    "tech": "unknown",
                    "type": "lte",
                })
    except Exception as e:
        logger.debug("[Cellular] mmcli error: %s", e)
    return results


def guess_operator_from_ssid(ssid: str) -> Optional[str]:
    """P13: Guess operator from WiFi SSID."""
    ssid_upper = (ssid or "").upper()
    if "MTS" in ssid_upper or "МТС" in ssid_upper:
        return "MTS"
    if "MEGAFON" in ssid_upper or "МЕГАФОН" in ssid_upper or "MEGA" in ssid_upper:
        return "MegaFon"
    if "BEELINE" in ssid_upper or "БИЛАЙН" in ssid_upper or "BEEL" in ssid_upper:
        return "Beeline"
    if "TELE2" in ssid_upper or "ТЕЛЕ2" in ssid_upper:
        return "Tele2"
    if "YOTA" in ssid_upper or "ЙОТА" in ssid_upper:
        return "Yota"
    if "ROSTELECOM" in ssid_upper or "РОСТЕЛЕКОМ" in ssid_upper:
        return "Rostelecom"
    return None


def lookup_operator(mcc: str, mnc: str) -> Optional[str]:
    """Lookup operator by MCC/MNC."""
    key = str(mcc).zfill(3) + str(mnc).zfill(2)
    return OPERATORS.get(key)


def scan_cellular_via_wifi() -> List[Dict[str, Any]]:
    """P13: Guess cellular operator via WiFi SSIDs.

    Many mobile operators have branded WiFi routers.
    """
    results = []
    try:
        r = subprocess.run(
            ["netsh", "wlan", "show", "networks"],
            capture_output=True, timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            raw = r.stdout.decode("cp866", errors="replace")
        except Exception:
            raw = r.stdout.decode("utf-8", errors="replace")

        seen_ops = set()
        for line in raw.splitlines():
            if "SSID" in line and ":" in line:
                ssid = line.split(":", 1)[1].strip()
                op = guess_operator_from_ssid(ssid)
                if op and op not in seen_ops:
                    seen_ops.add(op)
                    results.append({
                        "operator": op,
                        "tech": "via_wifi",
                        "type": "cellular",
                        "source": "wifi_ssid:" + ssid,
                    })
    except Exception as e:
        logger.debug("[Cellular] wifi guess error: %s", e)
    return results


def geolocate_via_wifi() -> Optional[Dict[str, float]]:
    """P13: Geolocate by WiFi BSSIDs (Mozilla Location Service).

    Returns {lat, lon, accuracy_m} or None.
    """
    try:
        # Get WiFi BSSIDs
        r = subprocess.run(
            ["netsh", "wlan", "show", "networks", "mode=bssid"],
            capture_output=True, timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            raw = r.stdout.decode("cp866", errors="replace")
        except Exception:
            raw = r.stdout.decode("utf-8", errors="replace")

        bssids = re.findall(r"([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}", raw)
        if not bssids:
            return None

        # Mozilla Location Service API
        payload = json.dumps({
            "wifiAccessPoints": [
                {"macAddress": b.upper().replace("-", ":")} for b in bssids[:10]
            ]
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://location.services.mozilla.com/v1/geolocate?key=test",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            loc = data.get("location", {})
            if "lat" in loc and "lng" in loc:
                return {
                    "lat": loc["lat"],
                    "lon": loc["lng"],
                    "accuracy_m": loc.get("accuracy", 1000),
                }
    except Exception as e:
        logger.debug("[Cellular] geolocate error: %s", e)
    return None


def full_cellular_scan() -> Dict[str, Any]:
    """P13: Full cellular scan - modem + WiFi guess + geolocation."""
    return {
        "modem": scan_cellular(),
        "via_wifi": scan_cellular_via_wifi(),
        "location": geolocate_via_wifi(),
    }


if __name__ == "__main__":
    print("Testing cellular_scanner...")
    print("Modem scan:", scan_cellular())
    print("WiFi guess:", scan_cellular_via_wifi())
    loc = geolocate_via_wifi()
    print("Location:", loc)
    print("Full:", full_cellular_scan())
    print("cellular_scanner OK")
'@

    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($cellPath, $cellCode, $utf8)
    Write-Host "[OK] Created: cellular_scanner.py" -ForegroundColor Green

    python -c "import ast; ast.parse(open(r'$cellPath', encoding='utf-8').read()); print('OK')"
}

# ============================================================
# 2. Add API endpoints to web/app.py
# ============================================================
$appPath = Join-Path $ProjectRoot "web\app.py"
$app = [System.IO.File]::ReadAllText($appPath, [System.Text.Encoding]::UTF8)
$app = $app -replace "`r`n", "`n"

if ($app.Contains("/api/cellular/scan")) {
    Write-Host "[--] Cellular endpoints already present" -ForegroundColor Yellow
} else {
    $newEndpoints = @'
@app.route('/api/cellular/scan', methods=['POST'])
def api_cellular_scan():
    """P13: Full cellular scan."""
    try:
        from inevionet.network.cellular_scanner import full_cellular_scan
        result = full_cellular_scan()
        # Add nodes for found operators
        for op in result.get('via_wifi', []):
            nid = 'cell_' + op.get('operator', 'unknown').lower()
            upsert({
                'node_id': nid,
                'name': op.get('operator', 'Cell'),
                'label': op.get('operator', 'Cell')[:20],
                'type': 'cellular',
                'ip': 'unknown', 'port': 0,
                'trust': 60.0, 'packets': 0, 'online': True,
                'rssi': -85, 'signal': 40,
                'method': 'cellular_via_wifi', 'evolving': False,
                'parent': None,
            })
        for cell in result.get('modem', []):
            nid = 'cell_modem_' + str(cell.get('cell_id', 'unknown'))[:16]
            upsert({
                'node_id': nid,
                'name': cell.get('operator', 'Cell') + ' (' + cell.get('tech', '?') + ')',
                'label': cell.get('operator', 'Cell')[:20],
                'type': 'cellular',
                'ip': 'unknown', 'port': 0,
                'trust': 70.0, 'packets': 0, 'online': True,
                'rssi': -75, 'signal': 60,
                'method': 'modem', 'evolving': False,
                'parent': None,
            })
        return jsonify({'success': True, **result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/cellular/locate')
def api_cellular_locate():
    """P13: Geolocate via WiFi."""
    try:
        from inevionet.network.cellular_scanner import geolocate_via_wifi
        loc = geolocate_via_wifi()
        return jsonify({'success': bool(loc), 'location': loc})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/cellular/operator')
def api_cellular_operator():
    """P13: Guess operator from WiFi."""
    try:
        from inevionet.network.cellular_scanner import scan_cellular_via_wifi
        ops = scan_cellular_via_wifi()
        return jsonify({'success': True, 'operators': ops})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


'@

    $marker = "@socketio.on('connect')"
    $pos = $app.IndexOf($marker)
    if ($pos -gt 0) {
        $app = $app.Substring(0, $pos) + $newEndpoints + $app.Substring($pos)
        $utf8 = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($appPath, $app, $utf8)
        Write-Host "[OK] Cellular endpoints added" -ForegroundColor Green
        python -c "import ast; ast.parse(open(r'$appPath', encoding='utf-8').read()); print('OK')"
    }
}

# ============================================================
# 3. Add UI card
# ============================================================
$htmlPath = Join-Path $ProjectRoot "web\templates\index.html"
$html = [System.IO.File]::ReadAllText($htmlPath, [System.Text.Encoding]::UTF8)
$html = $html -replace "`r`n", "`n"

if ($html.Contains("cellularTarget")) {
    Write-Host "[--] Cellular UI already present" -ForegroundColor Yellow
} else {
    $newCard = @'
<div class="card">
<h3>Cellular</h3>
<button class="btn secondary" onclick="scanCellular()">Scan LTE/5G</button>
<button class="btn small" onclick="locateMe()">Locate me</button>
<div id="cellularResult"></div>
</div>

'@

    $logMarker = 'id="logContainer"'
    $logPos = $html.IndexOf($logMarker)
    if ($logPos -gt 0) {
        $backPos = $html.LastIndexOf('<div class="card">', $logPos)
        if ($backPos -gt 0) {
            $html = $html.Substring(0, $backPos) + $newCard + $html.Substring($backPos)
            Write-Host "[OK] Cellular UI card added" -ForegroundColor Green
        }
    }

    $newJS = @'
async function scanCellular() {
    addLog('Cellular scan...', 'info');
    const el = document.getElementById('cellularResult');
    el.textContent = 'Scanning...';
    try {
        const r = await fetch('/api/cellular/scan', { method: 'POST' });
        const d = await r.json();
        if (d.success) {
            const modem = (d.modem || []).length;
            const viaWifi = (d.via_wifi || []).length;
            let txt = 'Modem: ' + modem + ' | WiFi: ' + viaWifi;
            if (d.location) {
                txt += ' | Loc: ' + d.location.lat.toFixed(4) + ',' + d.location.lon.toFixed(4);
            }
            el.textContent = txt;
            addLog('Cellular: ' + txt, 'success');
        } else {
            el.textContent = 'Error: ' + d.error;
        }
    } catch (e) {
        addLog('Cellular: ' + e, 'error');
    }
}

async function locateMe() {
    addLog('Geolocating via WiFi...', 'info');
    const el = document.getElementById('cellularResult');
    try {
        const r = await fetch('/api/cellular/locate');
        const d = await r.json();
        if (d.success && d.location) {
            el.textContent = 'Location: ' + d.location.lat.toFixed(5) + ', ' +
                d.location.lon.toFixed(5) + ' (±' + d.location.accuracy_m + 'm)';
            addLog('Located: ' + el.textContent, 'success');
        } else {
            el.textContent = 'Location not available';
            addLog('Location not found', 'warn');
        }
    } catch (e) {
        addLog('Locate: ' + e, 'error');
    }
}

'@

    $jsMarker = "checkAuth();"
    $jsPos = $html.IndexOf($jsMarker)
    if ($jsPos -gt 0) {
        $html = $html.Substring(0, $jsPos) + $newJS + $html.Substring($jsPos)
        Write-Host "[OK] Cellular JS added" -ForegroundColor Green
    }

    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($htmlPath, $html, $utf8)
    Write-Host "[OK] index.html saved" -ForegroundColor Green
}

Write-Host ""
Write-Host "Testing cellular_scanner..." -ForegroundColor Cyan
python -c "from inevionet.network.cellular_scanner import scan_cellular, scan_cellular_via_wifi, geolocate_via_wifi; print('Modem:', scan_cellular()); print('WiFi guess:', scan_cellular_via_wifi()); print('Location:', geolocate_via_wifi())"

Write-Host ""
Write-Host "Done! Restart: python -m web.app" -ForegroundColor Green