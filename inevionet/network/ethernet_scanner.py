"""P36: Ethernet scanner for industrial protocols (Modbus/MQTT/OPC-UA/DNP3)."""
import socket
import concurrent.futures
from typing import List, Dict, Any

from ..core.logger import get_logger

logger = get_logger("inevionet.network.ethernet_scanner")

INDUSTRIAL_PORTS = {
    502: "modbus",
    1883: "mqtt",
    8883: "mqtt_ssl",
    4840: "opcua",
    20000: "dnp3",
    44818: "ethernet_ip",
    102: "s7comm",
    2404: "iec104",
}


def scan_ethernet_subnet(subnet: str = None, timeout: float = 0.5,
                         max_workers: int = 128) -> List[Dict[str, Any]]:
    """P36: scan Ethernet subnet for industrial protocol ports."""
    if subnet is None:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            subnet = ".".join(local_ip.split(".")[:3])
        except Exception:
            subnet = "192.168.1"

    logger.info("[EthScan] scanning %s.1-254 for industrial ports", subnet)

    results = []

    def check_host(ip):
        found = []
        for port, proto in INDUSTRIAL_PORTS.items():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(timeout)
                r = s.connect_ex((ip, port))
                s.close()
                if r == 0:
                    found.append({"port": port, "protocol": proto})
            except Exception:
                pass
        if found:
            return {"ip": ip, "services": found}
        return None

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(check_host, f"{subnet}.{i}"): i for i in range(1, 255)}
            for fut in concurrent.futures.as_completed(futures):
                try:
                    res = fut.result()
                    if res:
                        results.append(res)
                        logger.info("[EthScan] found: %s -> %s",
                                    res["ip"], [s["protocol"] for s in res["services"]])
                except Exception:
                    pass
    except Exception as e:
        logger.error("[EthScan] error: %s", e)

    logger.info("[EthScan] total: %d hosts with industrial ports", len(results))
    return results


def get_ethernet_interfaces() -> List[Dict[str, Any]]:
    """P36: list Ethernet interfaces (not WiFi)."""
    import subprocess
    import json
    ifaces = []
    try:
        r = subprocess.run(
            ["powershell", "-Command",
             "Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | "
             "Select-Object Name, InterfaceDescription, LinkSpeed, MacAddress | "
             "ConvertTo-Json"],
            capture_output=True, text=True, timeout=10,
            encoding="utf-8", errors="ignore")
        data = json.loads(r.stdout) if r.stdout.strip() else []
        if isinstance(data, dict):
            data = [data]
        for iface in data:
            name = iface.get("Name", "")
            desc = iface.get("InterfaceDescription", "")
            # P37b: filter by description (WiFi)
            desc_low = desc.lower()
            name_low = name.lower()
            if any(x in desc_low for x in ("wi-fi", "wireless", "802.11")):
                continue
            if any(x in name_low for x in ("wi-fi", "wireless", "wlan")):
                continue
            ifaces.append({
                "name": name,
                "description": desc,
                "mac": iface.get("MacAddress", ""),
                "speed": iface.get("LinkSpeed", ""),
            })
    except Exception as e:
        logger.debug("[EthScan] ifaces error: %s", e)
    return ifaces
