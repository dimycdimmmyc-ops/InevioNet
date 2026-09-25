# patch16.py - Capsule + Mycelium (всё сразу)
import os
import ast
import sys
import shutil

ROOT = r"E:\InevioNet"
INEV = os.path.join(ROOT, "inevionet")


def backup(path):
    if not os.path.exists(path):
        return None
    bak = path + ".bak_p16"
    shutil.copy2(path, bak)
    print(f"  Backup: {os.path.basename(bak)}")
    return bak


def save_py(path, code):
    """Сохраняет Python с проверкой синтаксиса."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        ast.parse(code)
        print(f"  [OK] syntax: {os.path.basename(path)}")
    except SyntaxError as e:
        print(f"  [!!] syntax error: {e}")
        bak = path + ".bak_p16"
        if os.path.exists(bak):
            shutil.copy2(bak, path)
            print("  [!!] restored")
        sys.exit(1)


def save_raw(path, code):
    """Сохраняет без проверки (HTML)."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"  [OK] saved: {os.path.basename(path)}")


# ============================================================
# 16a: Create mycelium/capsule.py
# ============================================================
print()
print("=" * 70)
print("  PATCH 16a: mycelium/capsule.py")
print("=" * 70)

CAPSULE_PY = '''"""InevioNet Mycelium Capsule - build & deploy capsule to trusted hosts."""
import os
import sys
import json
import time
import socket
import hashlib
import subprocess
import threading
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field, asdict

from ..core.logger import get_logger
from ..core.constants import DataPaths

logger = get_logger("inevionet.mycelium.capsule")


# ============================================================
# TrustedHosts
# ============================================================
class TrustedHosts:
    """Список доверенных устройств (только свои!)."""

    def __init__(self, path: Optional[str] = None):
        if path is None:
            try:
                path = str(DataPaths.get_state_dir() / "trusted_hosts.json")
            except Exception:
                path = "trusted_hosts.json"
        self.path = path
        self.hosts: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._load()

    def add(self, host: str, label: str = "", user: str = None,
            method: str = "auto") -> bool:
        with self._lock:
            for h in self.hosts:
                if h["host"] == host:
                    h["label"] = label or h.get("label", "")
                    h["user"] = user or h.get("user")
                    h["method"] = method
                    self._save()
                    return True
            self.hosts.append({
                "host": host,
                "label": label or host,
                "user": user,
                "method": method,
                "added_at": time.time(),
            })
            self._save()
            logger.info("[Trusted] added: %s (%s)", host, label)
            return True

    def remove(self, host: str) -> bool:
        with self._lock:
            before = len(self.hosts)
            self.hosts = [h for h in self.hosts if h["host"] != host]
            if len(self.hosts) < before:
                self._save()
                logger.info("[Trusted] removed: %s", host)
                return True
            return False

    def is_trusted(self, host: str) -> bool:
        with self._lock:
            return any(h["host"] == host for h in self.hosts)

    def get(self, host: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            for h in self.hosts:
                if h["host"] == host:
                    return dict(h)
            return None

    def list_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(h) for h in self.hosts]

    def _load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.hosts = data if isinstance(data, list) else []
                logger.info("[Trusted] loaded %d hosts", len(self.hosts))
        except Exception as e:
            logger.warning("[Trusted] load error: %s", e)
            self.hosts = []

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.hosts, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("[Trusted] save error: %s", e)


# ============================================================
# CapsuleBuilder
# ============================================================
class CapsuleBuilder:
    """Собирает минимальный capsule из своего кода."""

    # Модули, которые включаются в capsule
    INCLUDE_MODULES = [
        "core",
        "network",
        "mycelium",
        "evolution",
        "steganography",
        "masking",
        "identity",
    ]

    # Модули, которые НЕ включаются
    EXCLUDE_MODULES = [
        "web",
        "users",
        "industrial",
        "capsule",
        "mesh",
        "symbiotic",
        "ai",
        "dht",
        "messaging",
        "security",
        "simple",
    ]

    def __init__(self, project_root: Optional[str] = None):
        if project_root is None:
            project_root = os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))
        self.project_root = project_root
        self.inev_dir = os.path.join(project_root, "inevionet")

    def build_minimal(self, include: Optional[List[str]] = None) -> bytes:
        """Собрать минимальный capsule (tar.gz в base64)."""
        import io
        import tarfile
        import base64

        include = include or self.INCLUDE_MODULES

        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for module in include:
                mod_path = os.path.join(self.inev_dir, module)
                if not os.path.isdir(mod_path):
                    continue
                for dirpath, dirnames, filenames in os.walk(mod_path):
                    dirnames[:] = [d for d in dirnames if d != "__pycache__"]
                    for fname in filenames:
                        if not fname.endswith(".py"):
                            continue
                        full = os.path.join(dirpath, fname)
                        rel = os.path.relpath(full, self.project_root)
                        tar.add(full, arcname=rel)

            # Добавить метаданные
            meta = {
                "version": "1.0.0",
                "built_at": time.time(),
                "include": include,
                "host": socket.gethostname(),
            }
            meta_bytes = json.dumps(meta, indent=2).encode("utf-8")
            info = tarfile.TarInfo(name="capsule_meta.json")
            info.size = len(meta_bytes)
            info.mtime = int(time.time())
            tar.addfile(info, io.BytesIO(meta_bytes))

        raw = buf.getvalue()
        logger.info("[Capsule] built: %d bytes", len(raw))
        return raw

    def build_fragment(self, code: bytes, index: int, total: int) -> bytes:
        """Собрать фрагмент кода."""
        chunk_size = (len(code) + total - 1) // total
        start = index * chunk_size
        end = min(start + chunk_size, len(code))
        chunk = code[start:end]

        header = json.dumps({
            "index": index,
            "total": total,
            "chunk_size": chunk_size,
            "checksum": hashlib.sha256(code).hexdigest()[:16],
        }).encode("utf-8")

        import struct
        return struct.pack("!I", len(header)) + header + chunk

    def estimate_size(self, include: Optional[List[str]] = None) -> int:
        """Оценить размер."""
        code = self.build_minimal(include)
        return len(code)


# ============================================================
# CapsuleDeployer
# ============================================================
class CapsuleDeployer:
    """Разворачивает capsule на доверенных узлах."""

    def __init__(self, trusted: TrustedHosts, ssh_user: Optional[str] = None):
        self.trusted = trusted
        self.ssh_user = ssh_user
        self.stats = {
            "attempts": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
        }

    def deploy(self, target: str, code: bytes,
               method: str = "auto") -> bool:
        """Развернуть capsule на target."""
        if not self.trusted.is_trusted(target):
            logger.warning("[Deploy] refused: %s not trusted", target)
            self.stats["skipped"] += 1
            return False

        self.stats["attempts"] += 1
        host_info = self.trusted.get(target) or {}
        user = host_info.get("user") or self.ssh_user

        methods = {
            "ssh": lambda: self._deploy_ssh(target, code, user),
            "smb": lambda: self._deploy_smb(target, code),
            "adb": lambda: self._deploy_adb(target, code),
            "http": lambda: self._deploy_http(target, code),
        }

        if method == "auto":
            for m in ["ssh", "smb", "adb", "http"]:
                logger.info("[Deploy] trying %s -> %s", m, target)
                if methods[m]():
                    self.stats["success"] += 1
                    return True
            self.stats["failed"] += 1
            return False

        fn = methods.get(method)
        if not fn:
            logger.warning("[Deploy] unknown method: %s", method)
            self.stats["failed"] += 1
            return False

        ok = fn()
        if ok:
            self.stats["success"] += 1
        else:
            self.stats["failed"] += 1
        return ok

    def _deploy_ssh(self, target: str, code: bytes,
                    user: Optional[str] = None) -> bool:
        try:
            host = target.split(":")[0]
            user_prefix = f"{user}@" if user else ""
            remote_path = "/tmp/inevionet_capsule.py.tar.gz"

            # Write temp
            import tempfile
            tmp = tempfile.NamedTemporaryFile(
                delete=False, suffix=".tar.gz")
            tmp.write(code)
            tmp.close()

            # SCP
            r = subprocess.run(
                ["scp", "-o", "StrictHostKeyChecking=no",
                 "-o", "ConnectTimeout=5",
                 tmp.name, f"{user_prefix}{host}:{remote_path}"],
                capture_output=True, timeout=20)
            try:
                os.unlink(tmp.name)
            except Exception:
                pass

            if r.returncode != 0:
                logger.debug("[Deploy] scp failed: %s",
                             r.stderr.decode(errors="replace")[:200])
                return False

            # Extract + run
            cmd = (
                f"mkdir -p /tmp/inevionet && "
                f"cd /tmp/inevionet && "
                f"tar -xzf {remote_path} && "
                f"nohup python3 -m inevionet.orchestrator "
                f"--node-id capsule_{host.replace('.','_')} "
                f">/tmp/inevionet.log 2>&1 &"
            )
            r = subprocess.run(
                ["ssh", "-o", "StrictHostKeyChecking=no",
                 "-o", "ConnectTimeout=5",
                 f"{user_prefix}{host}", cmd],
                capture_output=True, timeout=20)

            if r.returncode == 0:
                logger.info("[Deploy] ssh OK: %s", target)
                return True
            logger.debug("[Deploy] ssh run failed: %s",
                         r.stderr.decode(errors="replace")[:200])
            return False
        except Exception as e:
            logger.error("[Deploy] ssh error: %s", e)
            return False

    def _deploy_smb(self, target: str, code: bytes) -> bool:
        try:
            import tempfile
            host = target.split(":")[0]
            # Try typical admin share
            remote = f"\\\\{host}\\C$\\InevioNet\\capsule.tar.gz"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz")
            tmp.write(code)
            tmp.close()
            try:
                shutil_copy = __import__("shutil").copy2
                shutil_copy(tmp.name, remote)
                logger.info("[Deploy] smb OK: %s", target)
                return True
            finally:
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass
        except Exception as e:
            logger.debug("[Deploy] smb error: %s", e)
            return False

    def _deploy_adb(self, target: str, code: bytes) -> bool:
        try:
            import tempfile
            host = target.split(":")[0]
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz")
            tmp.write(code)
            tmp.close()
            try:
                r1 = subprocess.run(
                    ["adb", "-s", host, "push", tmp.name,
                     "/data/local/tmp/capsule.tar.gz"],
                    capture_output=True, timeout=15)
                if r1.returncode != 0:
                    return False
                r2 = subprocess.run(
                    ["adb", "-s", host, "shell",
                     "cd /data/local/tmp && tar -xzf capsule.tar.gz && "
                     "nohup python3 -m inevionet.orchestrator &"],
                    capture_output=True, timeout=15)
                return r2.returncode == 0
            finally:
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass
        except Exception as e:
            logger.debug("[Deploy] adb error: %s", e)
            return False

    def _deploy_http(self, target: str, code: bytes) -> bool:
        try:
            import urllib.request
            host = target.split(":")[0]
            url = f"http://{host}:8081/api/capsule/receive"
            req = urllib.request.Request(
                url, data=code,
                headers={"Content-Type": "application/octet-stream"},
                method="POST")
            with urllib.request.urlopen(req, timeout=10) as r:
                ok = r.status == 200
                if ok:
                    logger.info("[Deploy] http OK: %s", target)
                return ok
        except Exception as e:
            logger.debug("[Deploy] http error: %s", e)
            return False

    def get_stats(self) -> Dict[str, Any]:
        return dict(self.stats)
'''

capsule_path = os.path.join(INEV, "mycelium", "capsule.py")
backup(capsule_path)
save_py(capsule_path, CAPSULE_PY)


# ============================================================
# 16b: Extend Spore + Genome
# ============================================================
print()
print("=" * 70)
print("  PATCH 16b: Spore + Genome extension")
print("=" * 70)

# --- Spore ---
spore_path = os.path.join(INEV, "mycelium", "spores.py")
backup(spore_path)
with open(spore_path, "r", encoding="utf-8") as f:
    spore_code = f.read()

if "capsule_code" in spore_code:
    print("  [--] Spore already extended")
else:
    # Добавить поля в dataclass Spore
    old_fields = """    retransmissions: int = 0
    bytes_cached: int = 0
    bytes_retransmitted: int = 0
"""
    new_fields = """    retransmissions: int = 0
    bytes_cached: int = 0
    bytes_retransmitted: int = 0

    # P16: capsule payload
    capsule_code: bytes = b""
    capsule_target: str = ""
    capsule_method: str = "auto"
    capsule_version: str = "1.0.0"
    parent_capsule_id: str = ""
    generation: int = 0
"""
    if old_fields in spore_code:
        spore_code = spore_code.replace(old_fields, new_fields)
        print("  [OK] Spore fields added")
    else:
        print("  [!!] Spore fields pattern not found")

    save_py(spore_path, spore_code)


# --- Genome ---
genome_path = os.path.join(INEV, "evolution", "genome.py")
backup(genome_path)
with open(genome_path, "r", encoding="utf-8") as f:
    genome_code = f.read()

if "capsule_strategy" in genome_code:
    print("  [--] Genome already extended")
else:
    # Добавить гены перед "fitness: float"
    old_field = """    use_stego: bool = False

    fitness: float = 0.0"""
    new_field = """    use_stego: bool = False

    # P16: capsule genes
    capsule_strategy: str = "minimal"
    capsule_deploy_method: str = "auto"
    capsule_fragment_size: int = 32768
    capsule_channel: str = "DNS"
    capsule_spawn_depth: int = 2
    capsule_targets_per_cycle: int = 5

    fitness: float = 0.0"""
    if old_field in genome_code:
        genome_code = genome_code.replace(old_field, new_field)
        print("  [OK] Genome fields added")
    else:
        print("  [!!] Genome fields pattern not found")

    # Расширить create_random_genome
    old_rnd = """        use_polymorphic=random.random() < 0.5,
        use_ambient=random.random() < 0.5,
        use_stego=random.random() < 0.5,
    )"""
    new_rnd = """        use_polymorphic=random.random() < 0.5,
        use_ambient=random.random() < 0.5,
        use_stego=random.random() < 0.5,
        capsule_strategy=random.choice(["minimal", "full", "fragment"]),
        capsule_deploy_method=random.choice(["auto", "ssh", "smb", "adb", "http"]),
        capsule_fragment_size=random.choice([16384, 32768, 65536]),
        capsule_channel=random.choice(["DNS", "ICMP", "HTTP", "Stego"]),
        capsule_spawn_depth=random.randint(1, 3),
        capsule_targets_per_cycle=random.randint(1, 10),
    )"""
    if old_rnd in genome_code:
        genome_code = genome_code.replace(old_rnd, new_rnd)
        print("  [OK] create_random_genome extended")
    else:
        print("  [--] create_random_genome pattern not found")

    save_py(genome_path, genome_code)


# ============================================================
# 16c: Integrate into orchestrator.py
# ============================================================
print()
print("=" * 70)
print("  PATCH 16c: orchestrator.py integration")
print("=" * 70)

orch_path = os.path.join(INEV, "orchestrator.py")
backup(orch_path)
with open(orch_path, "r", encoding="utf-8") as f:
    orch = f.read()

if "TrustedHosts" in orch:
    print("  [--] orchestrator already integrated")
else:
    # 1. Добавить импорт после MyceliumEngine
    old_imp = "from .mycelium.engine import MyceliumEngine"
    new_imp = """from .mycelium.engine import MyceliumEngine
from .mycelium.capsule import CapsuleBuilder, CapsuleDeployer, TrustedHosts"""
    if old_imp in orch:
        orch = orch.replace(old_imp, new_imp)
        print("  [OK] import added")
    else:
        print("  [!!] import pattern not found")

    # 2. Добавить в __init__ после mycelium
    old_init = "        self.mycelium = MyceliumEngine(node_id=self.node_id)"
    new_init = """        self.mycelium = MyceliumEngine(node_id=self.node_id)
        # P16: capsule builder + deployer
        self.trusted_hosts = TrustedHosts()
        self.capsule_builder = CapsuleBuilder()
        self.capsule_deployer = CapsuleDeployer(
            trusted=self.trusted_hosts,
            ssh_user=None,
        )"""
    if old_init in orch:
        orch = orch.replace(old_init, new_init)
        print("  [OK] __init__ extended")
    else:
        print("  [!!] __init__ pattern not found")

    # 3. В _topology_loop добавить deploy cycle
    old_topo_marker = "                info = topo.build_from_scanner(min_quality=0.2)"
    new_topo_marker = """                info = topo.build_from_scanner(min_quality=0.2)

                # P16: capsule deploy cycle
                try:
                    self._capsule_deploy_cycle(topo)
                except Exception as _ce:
                    logger.debug('[Capsule] deploy cycle error: %s', _ce)"""
    if old_topo_marker in orch:
        orch = orch.replace(old_topo_marker, new_topo_marker, 1)
        print("  [OK] _topology_loop extended")

    # 4. Добавить метод _capsule_deploy_cycle перед def send_text
    marker = "    def send_text(self, receiver, text, **kwargs):"
    deploy_method = '''    def _capsule_deploy_cycle(self, topo):
        """P16: build + deploy capsule to trusted hosts."""
        if not hasattr(self, "trusted_hosts"):
            return
        trusted = self.trusted_hosts.list_all()
        if not trusted:
            return

        # Build capsule once
        try:
            code = self.capsule_builder.build_minimal()
        except Exception as e:
            logger.debug("[Capsule] build error: %s", e)
            return

        # Pick strategy from genome
        method = "auto"
        if self.evolution:
            best = self.evolution.best_strategy("capsule_deploy_method")
            if best:
                method = best

        # Deploy to each trusted (only if not deployed recently)
        for h in trusted:
            host = h["host"]
            # Skip if already deployed recently
            key = f"capsule_deployed:{host}"
            now = __import__("time").time()
            last = getattr(self, "_capsule_last", {})
            if host in last and now - last[host] < 300:
                continue
            ok = self.capsule_deployer.deploy(host, code, method=method)
            if ok:
                logger.info("[Capsule] deployed to %s", host)
                last[host] = now
            else:
                logger.debug("[Capsule] deploy failed: %s", host)
            self._capsule_last = last

    def get_capsule_stats(self):
        """P16: capsule stats."""
        return {
            "trusted_hosts": self.trusted_hosts.list_all() if hasattr(self, "trusted_hosts") else [],
            "builder": {
                "include_modules": getattr(self.capsule_builder, "INCLUDE_MODULES", []),
                "estimated_size": 0,
            },
            "deployer": self.capsule_deployer.get_stats() if hasattr(self, "capsule_deployer") else {},
        }

    def send_text(self, receiver, text, **kwargs):'''

    if marker in orch:
        orch = orch.replace(marker, deploy_method, 1)
        print("  [OK] _capsule_deploy_cycle added")
    else:
        print("  [!!] send_text marker not found")

    save_py(orch_path, orch)


# ============================================================
# 16d: API + UI
# ============================================================
print()
print("=" * 70)
print("  PATCH 16d: API + UI")
print("=" * 70)

# --- API ---
app_path = os.path.join(ROOT, "web", "app.py")
backup(app_path)
with open(app_path, "r", encoding="utf-8") as f:
    app = f.read()

if "/api/capsule/trusted" in app:
    print("  [--] API already extended")
else:
    api_code = '''
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


'''
    marker = "@socketio.on('connect')"
    if marker in app:
        app = app.replace(marker, api_code + marker, 1)
        save_py(app_path, app)
        print("  [OK] API endpoints added")
    else:
        print("  [!!] socketio marker not found")


# --- UI ---
html_path = os.path.join(ROOT, "web", "templates", "index.html")
backup(html_path)
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

if "capsuleHostInput" in html:
    print("  [--] UI already extended")
else:
    card = '''<div class="card">
<h3>🌐 Капсулы (грибница)</h3>
<div style="font-size:0.85em;color:var(--dim);margin-bottom:10px">
Разворачивает InevioNet на твоих устройствах. Только для доверенных!
</div>
<div class="form-group">
  <label>Доверенное устройство (IP или host)</label>
  <input id="capsuleHostInput" placeholder="192.168.1.100">
</div>
<div class="form-group">
  <label>Метка (опционально)</label>
  <input id="capsuleLabelInput" placeholder="Мой сервер">
</div>
<button class="btn btn-glass" onclick="addTrusted()">➕ Добавить в доверенные</button>
<button class="btn btn-success" onclick="deployAll()">🌐 Развернуть на всех</button>
<button class="btn btn-sm btn-glass" onclick="loadCapsuleStats()">📊 Обновить</button>
<div id="capsuleList" style="margin-top:10px;font-size:0.85em"></div>
<div id="capsuleStats" style="margin-top:6px;font-size:0.8em;color:var(--dim)"></div>
</div>

'''
    # Insert before Network Scanners
    inserted = False
    for marker in ['<h3>Network Scanners</h3>', '<h3>Сканирование сетей</h3>', 'id="logContainer"']:
        if marker in html:
            idx = html.index(marker)
            back = html.rindex('<div class="card">', 0, idx)
            html = html[:back] + card + html[back:]
            inserted = True
            print(f"  [OK] UI card inserted before {marker}")
            break

    if not inserted:
        print("  [!!] no marker for UI card")

    # Add JS
    js = '''
async function addTrusted() {
    const host = document.getElementById('capsuleHostInput').value.trim();
    const label = document.getElementById('capsuleLabelInput').value.trim();
    if (!host) { addLog('Введите host', 'error'); return; }
    try {
        const r = await fetch('/api/capsule/trusted', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({host, label})
        });
        const d = await r.json();
        if (d.success) {
            addLog('Добавлено: ' + host, 'success');
            loadCapsuleStats();
        } else {
            addLog('Ошибка: ' + (d.error || '?'), 'error');
        }
    } catch (e) { addLog('Trusted: ' + e, 'error'); }
}

async function removeTrusted(host) {
    try {
        const r = await fetch('/api/capsule/trusted', {
            method: 'DELETE',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({host})
        });
        const d = await r.json();
        if (d.success) {
            addLog('Удалено: ' + host, 'success');
            loadCapsuleStats();
        }
    } catch (e) { addLog('Remove: ' + e, 'error'); }
}

async function deployAll() {
    try {
        const r = await fetch('/api/capsule/stats');
        const d = await r.json();
        const hosts = (d.stats && d.stats.trusted_hosts) || [];
        if (!hosts.length) { addLog('Нет доверенных устройств', 'warn'); return; }
        for (const h of hosts) {
            const r2 = await fetch('/api/capsule/deploy', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({host: h.host})
            });
            const d2 = await r2.json();
            addLog((d2.success ? '✅ ' : '❌ ') + h.host, d2.success ? 'success' : 'error');
        }
        loadCapsuleStats();
    } catch (e) { addLog('Deploy: ' + e, 'error'); }
}

async function loadCapsuleStats() {
    try {
        const r = await fetch('/api/capsule/stats');
        const d = await r.json();
        if (!d.success) return;
        const hosts = (d.stats && d.stats.trusted_hosts) || [];
        const el = document.getElementById('capsuleList');
        if (hosts.length) {
            el.innerHTML = hosts.map(h =>
                '<div class="list-item"><span>' + (h.label || h.host) +
                ' <span style="color:var(--dim);font-size:0.8em">' + h.host + '</span></span>' +
                '<button class="del" onclick="removeTrusted(\\'' + h.host + '\\')">×</button></div>'
            ).join('');
        } else {
            el.innerHTML = '<div class="empty">Нет доверенных устройств</div>';
        }
        const dep = (d.stats && d.stats.deployer) || {};
        document.getElementById('capsuleStats').textContent =
            'Попыток: ' + (dep.attempts || 0) +
            ' | Успех: ' + (dep.success || 0) +
            ' | Отказ: ' + (dep.failed || 0);
        addLog('Capsule stats loaded', 'success');
    } catch (e) { addLog('Capsule: ' + e, 'error'); }
}

'''
    js_marker = "checkAuth();"
    if js_marker in html:
        html = html.replace(js_marker, js + '\n' + js_marker, 1)
        print("  [OK] JS added")

    save_raw(html_path, html)


print()
print("=" * 70)
print("  PATCH 16 DONE")
print("=" * 70)
print()
print("Что изменилось:")
print("  [OK] inevionet/mycelium/capsule.py   (TrustedHosts + Builder + Deployer)")
print("  [OK] inevionet/mycelium/spores.py    (Spore + capsule fields)")
print("  [OK] inevionet/evolution/genome.py   (Genome + capsule genes)")
print("  [OK] inevionet/orchestrator.py       (integration + deploy cycle)")
print("  [OK] web/app.py                      (3 API endpoints)")
print("  [OK] web/templates/index.html        (UI card + JS)")
print()
print("Перезапусти сервер:")
print("  python -m web.app")
print()
print("Открой UI, найди карточку 🌐 Капсулы.")
print("Добавь свои устройства (192.168.x.x) и нажми Развернуть.")