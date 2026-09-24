"""InevioNet Network Profile - P92a.

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
    """P92a + P92-fix2: эвристика типа сети."""
    svc = set(s.lower() for s in services)
    # Корпоративная: много SMB/RDP/AD
    if any(s in svc for s in ("smb", "rdp", "ldap", "kerberos", "netbios")):
        return "corporate"
    # Публичная: только mDNS/SSDP + очень мало устройств (1-2, без router)
    router = device_types.get("router", 0)
    if total_devices <= 2 and router == 0 and any(
            s in svc for s in ("mdns", "ssdp", "llmnr")):
        return "public"
    # P92-fix2: домашняя - router + >=1 device (включая "device"/unknown)
    iot = device_types.get("iot", 0)
    pc = device_types.get("pc", 0)
    generic = device_types.get("device", 0)
    phone = device_types.get("phone", 0)
    non_router = iot + pc + generic + phone
    if router >= 1 and non_router >= 1:
        return "home"
    # Fallback: если есть router, но мало devices - тоже home
    if router >= 1:
        return "home"
    # Fallback: если есть устройства без router - вероятно public
    if non_router >= 1:
        return "public"
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
