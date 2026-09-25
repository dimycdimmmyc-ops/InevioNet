# patch92.py - P92a+b+c+d: адаптивная маскировка через разведчиков
#   P92a: network_profile.py (build_network_profile)
#   P92b: Spore.network_profile + SporeManager.set_profile/get_profile
#   P92c: AmbientAnalyzer.feed_from_recon + get_merged_profile
#   P92d: AmbientMasker.adapt_to_network + get_network_profile
#   + orchestrator: вызовы в _full_scan_loop и _multi_channel_loop
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
INEV = os.path.join(ROOT, "inevionet")
MASK = os.path.join(INEV, "masking")
MYC = os.path.join(INEV, "mycelium")
ORCH = os.path.join(INEV, "orchestrator.py")
AMBIENT = os.path.join(MASK, "ambient.py")
SPORES = os.path.join(MYC, "spores.py")
NETPROF = os.path.join(MASK, "network_profile.py")

BAK = ".bak_p92"


def patch_file(path, replacements, label, bak=BAK):
    if not os.path.exists(path):
        print("  [!!] NOT FOUND: " + path)
        return False
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    b = path + bak
    shutil.copy2(path, b)
    print("  [BK] " + os.path.basename(b))
    changed = 0
    for old, new, required in replacements:
        # idempotency: new уже есть и old нет
        if new and new in content and (not old or old not in content):
            print("  [--] already applied")
            continue
        if old and old in content:
            content = content.replace(old, new, 1)
            changed += 1
            print("  [OK] " + old[:55].strip())
        else:
            if required:
                print("  [!!] NOT FOUND: " + old[:55].strip())
    if changed > 0:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        if path.endswith(".py"):
            try:
                ast.parse(content)
                print("  [OK] syntax " + label)
                return True
            except SyntaxError as e:
                print("  [!!] syntax: " + str(e))
                shutil.copy2(b, path)
                print("  [--] rolled back")
                return False
        else:
            print("  [OK] saved " + label)
            return True
    return True


def write_py(path, code, label):
    if os.path.exists(path):
        b = path + BAK
        shutil.copy2(path, b)
        print("  [BK] " + os.path.basename(b))
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        ast.parse(code)
        print("  [OK] " + label)
        return True
    except SyntaxError as e:
        print("  [!!] " + label + " syntax: " + str(e))
        b = path + BAK
        if os.path.exists(b):
            shutil.copy2(b, path)
            print("  [--] rolled back")
        return False


# =====================================================================
# P92a: network_profile.py - новый модуль
# =====================================================================

print()
print("=" * 70)
print("  P92a: network_profile.py")
print("=" * 70)

netprof_code = '''"""InevioNet Network Profile - P92a.

Собирает профиль сети из данных разведки:
  - local_map (ARP, devices, router)
  - traceroute hops (TTL -> OS hints)
  - mdns/ssdp/llmnr devices (services)
  - router_probe (firmware)

Возвращает dict для AmbientAnalyzer.feed_from_recon и Spore.network_profile.
"""
import time
from typing import Dict, List, Any, Optional

from ..core.logger import get_logger

logger = get_logger("inevionet.masking.network_profile")


# TTL -> OS hint
TTL_OS_HINTS = {
    64: "linux",
    128: "windows",
    255: "network",
}


def _classify_network(device_types: Dict[str, int],
                     services: List[str],
                     total_devices: int) -> str:
    """P92a: эвристика типа сети."""
    svc = set(s.lower() for s in services)
    # Корпоративная: много SMB/RDP/AD
    if any(s in svc for s in ("smb", "rdp", "ldap", "kerberos", "netbios")):
        return "corporate"
    # Публичная: только mDNS/SSDP + мало устройств, много HTTPS
    if total_devices <= 2 and any(s in svc for s in ("mdns", "ssdp", "llmnr")):
        return "public"
    # Домашняя: IoT + router + несколько PC
    iot = device_types.get("iot", 0)
    pc = device_types.get("pc", 0)
    if iot >= 1 or pc >= 1:
        return "home"
    return "unknown"


def build_network_profile(local_map: Optional[Dict[str, Any]] = None,
                          hops: Optional[List[Dict[str, Any]]] = None,
                          mdns_devices: Optional[List[Dict[str, Any]]] = None,
                          router_info: Optional[Dict[str, Any]] = None
                          ) -> Dict[str, Any]:
    """P92a: собрать профиль сети из данных разведки.

    Возвращает dict:
      network_type: home|corporate|public|unknown
      protocols: {HTTPS: 0.7, DNS: 0.2, ...}   (эвристика по типу сети)
      avg_packet_size: int
      avg_entropy: float
      ttl_typical: int (64/128/255)
      os_hints: {linux: N, windows: M}
      services: ["mdns", "ssdp", ...]
      device_types: {router: 1, pc: 3, iot: 2}
      total_devices: int
      unique_routers: int
      ts: float
    """
    profile: Dict[str, Any] = {
        "network_type": "unknown",
        "protocols": {},
        "avg_packet_size": 800,
        "avg_entropy": 0.7,
        "ttl_typical": 64,
        "os_hints": {},
        "services": [],
        "device_types": {},
        "total_devices": 0,
        "unique_routers": 0,
        "ts": time.time(),
    }

    # --- devices из local_map ---
    device_types: Dict[str, int] = {}
    total_devices = 0
    try:
        if local_map:
            devs = local_map.get("devices", []) or []
            total_devices = len(devs)
            for d in devs:
                dt = (d.get("type") or "device").lower()
                if dt in ("router", "gateway"):
                    key = "router"
                elif dt in ("phone", "mobile"):
                    key = "phone"
                elif dt in ("iot", "camera", "printer", "tv"):
                    key = "iot"
                elif dt in ("pc", "computer", "laptop"):
                    key = "pc"
                else:
                    key = "device"
                device_types[key] = device_types.get(key, 0) + 1
            # Сам роутер — из router_ip
            if local_map.get("router_ip") and "router" not in device_types:
                device_types["router"] = 1
    except Exception as e:
        logger.debug("[P92a] local_map: %s", e)

    # --- TTL из traceroute hops ---
    os_hints: Dict[str, int] = {}
    unique_routers = 0
    try:
        if hops:
            unique_routers = len({h.get("ip") for h in hops if h.get("ip")})
            for h in hops:
                ttl = h.get("ttl") or h.get("ttl_hint")
                if ttl:
                    os_name = TTL_OS_HINTS.get(int(ttl), "unknown")
                    os_hints[os_name] = os_hints.get(os_name, 0) + 1
    except Exception as e:
        logger.debug("[P92a] hops: %s", e)

    # --- services из mdns/ssdp ---
    services: List[str] = []
    try:
        if mdns_devices:
            srcs = set()
            for d in mdns_devices:
                s = (d.get("source") or "").lower()
                if s:
                    srcs.add(s)
                server = (d.get("server") or "").lower()
                if "windows" in server:
                    srcs.add("smb")
                if "linux" in server:
                    srcs.add("linux")
            services = sorted(srcs)
    except Exception as e:
        logger.debug("[P92a] mdns: %s", e)

    # --- network type ---
    network_type = _classify_network(device_types, services, total_devices)

    # --- protocols по типу сети (эвристика) ---
    if network_type == "corporate":
        protocols = {"HTTPS": 0.4, "SMB": 0.2, "RDP": 0.15,
                     "DNS": 0.15, "LDAP": 0.1}
        avg_size, avg_entropy = 700, 0.6
    elif network_type == "home":
        protocols = {"HTTPS": 0.65, "DNS": 0.15,
                     "HTTP": 0.1, "MDNS": 0.1}
        avg_size, avg_entropy = 900, 0.75
    elif network_type == "public":
        protocols = {"HTTPS": 0.8, "DNS": 0.15, "HTTP": 0.05}
        avg_size, avg_entropy = 1200, 0.85
    else:
        protocols = {"HTTPS": 0.7, "DNS": 0.2, "HTTP": 0.1}
        avg_size, avg_entropy = 1000, 0.8

    # TTL typical: большинство hop'ов
    ttl_typical = 64
    if os_hints:
        # Если windows больше linux — 128
        if os_hints.get("windows", 0) > os_hints.get("linux", 0):
            ttl_typical = 128

    profile.update({
        "network_type": network_type,
        "protocols": protocols,
        "avg_packet_size": avg_size,
        "avg_entropy": avg_entropy,
        "ttl_typical": ttl_typical,
        "os_hints": os_hints,
        "services": services,
        "device_types": device_types,
        "total_devices": total_devices,
        "unique_routers": unique_routers,
    })
    return profile
'''

write_py(NETPROF, netprof_code, "network_profile.py")


# =====================================================================
# P92b: spores.py - network_profile field + set/get
# =====================================================================

print()
print("=" * 70)
print("  P92b: Spore.network_profile + SporeManager.set/get_profile")
print("=" * 70)

# 1. Добавить поле в dataclass Spore (после map_data)
old_field = '''    # P38: map data (щупальце)
    map_data: Dict[str, Any] = field(default_factory=dict)
    probe_ttl: int = 5
    probe_time: float = 0.0
    is_probe: bool = False'''

new_field = '''    # P38: map data (щупальце)
    map_data: Dict[str, Any] = field(default_factory=dict)
    probe_ttl: int = 5
    probe_time: float = 0.0
    is_probe: bool = False

    # P92b: профиль сети (от разведчиков)
    network_profile: Dict[str, Any] = field(default_factory=dict)
    profile_updated: float = 0.0'''

patch_file(SPORES, [(old_field, new_field, True)], "spores.py Spore field")

# 2. Добавить set_profile/get_profile в SporeManager (после merge_map)
old_mm = '''    def merge_map(self, spore_id, map_data):
        """P38: merge map from spore."""
        spore = self.get(spore_id)
        if not spore:
            return False
        spore.map_data = map_data or {}
        spore.probe_time = time.time()
        if self.persist:
            self._save()
        return True'''

new_mm = '''    def merge_map(self, spore_id, map_data):
        """P38: merge map from spore."""
        spore = self.get(spore_id)
        if not spore:
            return False
        spore.map_data = map_data or {}
        spore.probe_time = time.time()
        if self.persist:
            self._save()
        return True

    def set_profile(self, spore_id, profile):
        """P92b: сохранить профиль сети в споре."""
        spore = self.get(spore_id)
        if not spore:
            return False
        spore.network_profile = dict(profile or {})
        spore.profile_updated = time.time()
        if self.persist:
            self._save()
        return True

    def get_profile(self, spore_id):
        """P92b: профиль сети из споры."""
        spore = self.get(spore_id)
        return dict(spore.network_profile) if spore else {}

    def set_profile_all(self, profile):
        """P92b: обновить профиль всем живым спорам."""
        n = 0
        with self._lock:
            for s in self.spores.values():
                if s.is_alive():
                    s.network_profile = dict(profile or {})
                    s.profile_updated = time.time()
                    n += 1
        if self.persist and n:
            self._save()
        return n

    def get_any_profile(self):
        """P92b: последний непустой профиль от спор."""
        best = None
        best_ts = 0.0
        with self._lock:
            for s in self.spores.values():
                if s.network_profile and s.profile_updated > best_ts:
                    best = dict(s.network_profile)
                    best_ts = s.profile_updated
        return best or {}'''

patch_file(SPORES, [(old_mm, new_mm, True)], "spores.py SporeManager methods")

# 3. to_dict - добавить network_profile
old_td = '''            "cache_size": len(self.cache),
            "retransmissions": self.retransmissions,
        }'''

new_td = '''            "cache_size": len(self.cache),
            "retransmissions": self.retransmissions,
            "network_profile": self.network_profile,
            "profile_updated": self.profile_updated,
        }'''

patch_file(SPORES, [(old_td, new_td, False)], "spores.py to_dict")

# 4. from_dict - загружать network_profile
old_fd = '''            last_used=data.get("last_used", time.time()),
            ttl=data.get("ttl", 3600.0))'''

new_fd = '''            last_used=data.get("last_used", time.time()),
            ttl=data.get("ttl", 3600.0),
            network_profile=data.get("network_profile", {}),
            profile_updated=data.get("profile_updated", 0.0))'''

patch_file(SPORES, [(old_fd, new_fd, False)], "spores.py from_dict")


# =====================================================================
# P92c: ambient.py - AmbientAnalyzer.feed_from_recon
# =====================================================================

print()
print("=" * 70)
print("  P92c: AmbientAnalyzer.feed_from_recon")
print("=" * 70)

# 1. Добавить _recon_profile в __init__
old_init = '''        self.stats = {"observations": 0, "last_update": 0.0}'''

new_init = '''        self.stats = {"observations": 0, "last_update": 0.0}
        # P92c: данные от разведчиков
        self._recon_profile = None
        self._recon_ts = 0.0
        self._recon_raw = {}'''

patch_file(AMBIENT, [(old_init, new_init, True)], "ambient.py _recon_profile")

# 2. Добавить feed_from_recon + get_merged_profile после observe_features
old_obs = '''    def observe_features(self, features):
        self.observe(features.size_bytes, features.protocol, features.entropy)'''

new_obs = '''    def observe_features(self, features):
        self.observe(features.size_bytes, features.protocol, features.entropy)

    def feed_from_recon(self, recon_data):
        """P92c: заполнить профиль из данных разведки.

        recon_data = {
          network_type, protocols, avg_packet_size, avg_entropy,
          ttl_typical, os_hints, services, device_types, total_devices,
          unique_routers, ...
        }
        """
        if not recon_data or not isinstance(recon_data, dict):
            return False
        self._recon_raw = dict(recon_data)
        self._recon_ts = time.time()
        # Синтезируем "наблюдения" из recon-профиля:
        # 1 наблюдение за протокол с весом = вероятность
        protocols = recon_data.get("protocols") or {}
        avg_size = int(recon_data.get("avg_packet_size", 800))
        avg_entropy = float(recon_data.get("avg_entropy", 0.7))
        # 5 семплов на каждый протокол — чтобы профиль ожил
        for proto, prob in protocols.items():
            try:
                weight = max(1, int(round(float(prob) * 10)))
            except Exception:
                weight = 1
            for _ in range(weight):
                self.observe(avg_size, proto, avg_entropy, interval_ms=100.0)
        self.stats["recon_feeds"] = self.stats.get("recon_feeds", 0) + 1
        return True

    def get_recon_profile(self):
        """P92c: последний recon-профиль."""
        return dict(self._recon_raw) if self._recon_raw else {}

    def get_network_type(self):
        """P92c: тип сети из recon."""
        return self._recon_raw.get("network_type", "unknown") if self._recon_raw else "unknown"

    def get_merged_profile(self):
        """P92c: профиль с учётом recon (если свой пуст — recon)."""
        p = self.get_profile()
        if p.total_packets == 0 and self._recon_raw:
            # Синтезировать профиль из recon
            proto = self._recon_raw.get("protocols") or {}
            dominant = max(proto, key=proto.get) if proto else "unknown"
            return AmbientProfile(
                timestamp=time.time(),
                total_packets=1,
                avg_size=float(self._recon_raw.get("avg_packet_size", 800)),
                avg_entropy=float(self._recon_raw.get("avg_entropy", 0.7)),
                dominant_protocol=dominant,
                typical_size=int(self._recon_raw.get("avg_packet_size", 800)),
                typical_entropy=float(self._recon_raw.get("avg_entropy", 0.7)),
                protocol_distribution=dict(proto),
            )
        return p'''

patch_file(AMBIENT, [(old_obs, new_obs, True)], "ambient.py feed_from_recon")


# =====================================================================
# P92d: ambient.py - AmbientMasker.adapt_to_network
# =====================================================================

print()
print("=" * 70)
print("  P92d: AmbientMasker.adapt_to_network")
print("=" * 70)

old_init2 = '''    def __init__(self, analyzer=None, adaptation_strength=0.7):
        self.analyzer = analyzer or AmbientAnalyzer()
        self.adaptation_strength = adaptation_strength
        self.adaptation_history = []'''

new_init2 = '''    def __init__(self, analyzer=None, adaptation_strength=0.7):
        self.analyzer = analyzer or AmbientAnalyzer()
        self.adaptation_strength = adaptation_strength
        self.adaptation_history = []
        # P92d: профиль сети (от разведчиков)
        self._network_profile = {}
        self._network_type = "unknown"'''

patch_file(AMBIENT, [(old_init2, new_init2, True)], "ambient.py masker init")

old_obs2 = '''    def observe(self, size, protocol, entropy, interval_ms=0.0):
        self.analyzer.observe(size, protocol, entropy, interval_ms)'''

new_obs2 = '''    def observe(self, size, protocol, entropy, interval_ms=0.0):
        self.analyzer.observe(size, protocol, entropy, interval_ms)

    def adapt_to_network(self, network_profile):
        """P92d: подстроить маскировку под профиль сети.

        network_profile = {network_type, protocols, avg_packet_size,
                           avg_entropy, ttl_typical, ...}
        """
        if not network_profile or not isinstance(network_profile, dict):
            return False
        self._network_profile = dict(network_profile)
        self._network_type = network_profile.get("network_type", "unknown")
        # Скорректировать силу адаптации:
        # corporate -> слабее (не выделяться), home -> среднее, public -> сильнее
        strength_map = {
            "corporate": 0.5,
            "home": 0.7,
            "public": 0.85,
            "unknown": 0.7,
        }
        self.adaptation_strength = strength_map.get(self._network_type, 0.7)
        # Передать recon в analyzer
        try:
            self.analyzer.feed_from_recon(network_profile)
        except Exception:
            pass
        self.adaptation_history.append({
            "event": "adapt_to_network",
            "network_type": self._network_type,
            "strength": self.adaptation_strength,
            "ts": time.time(),
        })
        logger.info("[P92d] adapted: type=%s strength=%.2f",
                    self._network_type, self.adaptation_strength)
        return True

    def get_network_profile(self):
        """P92d: текущий профиль сети."""
        return dict(self._network_profile) if self._network_profile else {}

    def get_network_type(self):
        """P92d: текущий тип сети."""
        return self._network_type'''

patch_file(AMBIENT, [(old_obs2, new_obs2, True)], "ambient.py masker adapt_to_network")


# =====================================================================
# orchestrator: P92c + P92b в _full_scan_loop, P92d в _multi_channel_loop
# =====================================================================

print()
print("=" * 70)
print("  orchestrator: вызовы P92")
print("=" * 70)

# P92c: feed_from_recon в _full_scan_loop — после add_wifi_devices
old_scan = '''                    # P90a: WiFi-устройства под роутером
                    try:
                        added = self.network_tree.add_wifi_devices(local)
                        if added:
                            logger.info("[P90a] added %d wifi devices", added)
                    except Exception as _we:
                        logger.debug("[P90a] %s", _we)'''

new_scan = '''                    # P90a: WiFi-устройства под роутером
                    try:
                        added = self.network_tree.add_wifi_devices(local)
                        if added:
                            logger.info("[P90a] added %d wifi devices", added)
                    except Exception as _we:
                        logger.debug("[P90a] %s", _we)
                    # P92: профиль сети -> analyzer + spores
                    try:
                        from .masking.network_profile import build_network_profile
                        _prof = build_network_profile(
                            local_map=local,
                            hops=tr_result.get("hops", []),
                            mdns_devices=mdns_result.get("devices", []),
                        )
                        _am = getattr(self, "_ambient_masker", None)
                        if _am is None:
                            # создать лениво
                            try:
                                self._ambient_masker = self._enable_ambient_masking_impl()
                                _am = self._ambient_masker
                            except Exception:
                                _am = None
                        if _am is not None:
                            _am.adapt_to_network(_prof)
                        # P92b: профиль в споры
                        try:
                            _sm = getattr(getattr(self, "mycelium", None), "spores", None)
                            if _sm is not None and hasattr(_sm, "set_profile_all"):
                                _n = _sm.set_profile_all(_prof)
                                if _n:
                                    logger.info("[P92b] profile -> %d spores (%s)",
                                                _n, _prof.get("network_type"))
                        except Exception as _se:
                            logger.debug("[P92b] %s", _se)
                    except Exception as _pe:
                        logger.debug("[P92] %s", _pe)'''

patch_file(ORCH, [(old_scan, new_scan, True)], "orchestrator P92c/P92b in _full_scan_loop")

# P92d: adapt_to_network в _multi_channel_loop — в начале try
old_mc = '''        while getattr(self, '_running', False):
            try:
                topo = getattr(self, "_auto_topology", None)
                if topo and hasattr(topo, 'nodes'):
                    # Собрать все каналы'''

new_mc = '''        while getattr(self, '_running', False):
            try:
                # P92d: периодически перечитывать профиль сети и адаптировать маскировку
                try:
                    _am = getattr(self, "_ambient_masker", None)
                    if _am is not None:
                        _p = _am.get_network_profile()
                        if not _p:
                            # попробовать у спор
                            _sm = getattr(getattr(self, "mycelium", None), "spores", None)
                            if _sm is not None and hasattr(_sm, "get_any_profile"):
                                _p = _sm.get_any_profile()
                        if _p:
                            _am.adapt_to_network(_p)
                except Exception as _ae:
                    logger.debug("[P92d] %s", _ae)

                topo = getattr(self, "_auto_topology", None)
                if topo and hasattr(topo, 'nodes'):
                    # Собрать все каналы'''

patch_file(ORCH, [(old_mc, new_mc, True)], "orchestrator P92d in _multi_channel_loop")


# =====================================================================
# app.py: endpoint /api/network/profile
# =====================================================================

print()
print("=" * 70)
print("  app.py: /api/network/profile")
print("=" * 70)

APP = os.path.join(ROOT, "web", "app.py")
anchor = "@app.route('/api/network/public')"

new_ep = '''@app.route('/api/network/profile')
def api_network_profile():
    """P92: профиль сети от разведчиков + маскировки."""
    try:
        n = get_net()
        out = {"success": True}
        # от masker
        am = getattr(n, "_ambient_masker", None)
        if am is not None:
            out["masker"] = {
                "network_type": am.get_network_type() if hasattr(am, "get_network_type") else "unknown",
                "profile": am.get_network_profile() if hasattr(am, "get_network_profile") else {},
                "strength": getattr(am, "adaptation_strength", None),
            }
        # от спор
        try:
            sm = getattr(getattr(n, "mycelium", None), "spores", None)
            if sm is not None and hasattr(sm, "get_any_profile"):
                out["spore_profile"] = sm.get_any_profile()
        except Exception:
            pass
        # из analyzer
        try:
            an = getattr(am, "analyzer", None) if am else None
            if an is not None and hasattr(an, "get_recon_profile"):
                out["recon"] = an.get_recon_profile()
        except Exception:
            pass
        return jsonify(out)
    except Exception as e:
        log.error('[P92] profile: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/public')'''

patch_file(APP, [(anchor, new_ep, True)], "app.py /api/network/profile")


print()
print("=" * 70)
print("  PATCH 92 DONE")
print("=" * 70)
print("  [OK] P92a: masking/network_profile.py (build_network_profile)")
print("  [OK] P92b: Spore.network_profile + set_profile_all/get_any_profile")
print("  [OK] P92c: AmbientAnalyzer.feed_from_recon + get_merged_profile")
print("  [OK] P92d: AmbientMasker.adapt_to_network + get_network_profile")
print("  [OK] orchestrator: P92c/P92b в _full_scan_loop, P92d в _multi_channel_loop")
print("  [OK] app.py: GET /api/network/profile")
print()
print("Перезапуск: python -m web.app")
print("Проверка:  curl -k https://localhost:8080/api/network/profile")