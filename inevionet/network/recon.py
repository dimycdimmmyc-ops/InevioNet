"""InevioNet Real Recon - real network recon via system utilities."""
import re, subprocess, time
from typing import Dict, Any
from ..core.logger import get_logger
log = get_logger("inevionet.network.recon")

class NetworkRecon:
    @staticmethod
    def dns_servers(host="example.com", timeout=6.0):
        out = {"servers": [], "type": "unknown", "ok": False}
        try:
            r = subprocess.run(["nslookup", host], capture_output=True, text=True,
                               timeout=timeout, encoding="utf-8", errors="replace")
            servers = list(dict.fromkeys(re.findall(r"Address:\s+(\d+\.\d+\.\d+\.\d+)", r.stdout or "")))
            out["servers"] = servers[:3]
            if servers:
                if any(s.startswith(("8.8.", "1.1.", "9.9.")) for s in servers): out["type"] = "public"
                elif any(s.startswith(("192.168.", "10.", "172.")) for s in servers): out["type"] = "local-resolver"
                else: out["type"] = "isp-resolver"
                out["ok"] = True
        except Exception as e:
            log.debug("[Recon] nslookup: %s", e)
        return out

    @staticmethod
    def route_trace(target="8.8.8.8", max_hops=5, timeout=15.0):
        out = {"hops": [], "depth": 0, "ok": False}
        try:
            r = subprocess.run(["tracert", "-d", "-h", str(max_hops), "-w", "800", target],
                               capture_output=True, text=True, timeout=timeout,
                               encoding="cp866", errors="replace")
            hops = [m.group(1) for m in (re.search(r"(\d+\.\d+\.\d+\.\d+)", l) for l in (r.stdout or "").splitlines()) if m]
            out["hops"] = hops; out["depth"] = len(hops); out["ok"] = bool(hops)
        except Exception as e:
            log.debug("[Recon] tracert: %s", e)
        return out

    @staticmethod
    def identify_isp(timeout=15.0):
        tokens = ("mts","beeline","megafon","tele2","rostelecom","rt.ru","mgts","ertelecom","dom.ru","t2","yota")
        try:
            r = subprocess.run(["tracert", "-h", "3", "-w", "800", "8.8.8.8"],
                               capture_output=True, text=True, timeout=timeout,
                               encoding="cp866", errors="replace")
            low = (r.stdout or "").lower()
            for t in tokens:
                if t in low: return t
        except Exception:
            pass
        return "unknown"

    @staticmethod
    def neighbors_estimate(timeout=5.0):
        try:
            r = subprocess.run(["arp", "-a"], capture_output=True, text=True,
                               timeout=timeout, encoding="cp866", errors="replace")
            return len(re.findall(r"([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}", r.stdout or ""))
        except Exception:
            return 0

    @staticmethod
    def _classify(ssid, dns_servers, hops):
        s = (ssid or "").lower()
        if any(k in s for k in ("5g","lte","mts","beeline","megafon","tele2")): return "cellular-router"
        if any(k in s for k in ("guest","public","free","cafe")): return "public-hotspot"
        if any(k in s for k in ("iot","smart","sensor","home")): return "iot-mesh"
        if any(k in s for k in ("corp","office","vpn","work")): return "corporate"
        if "8.8.8.8" in dns_servers or "1.1.1.1" in dns_servers: return "consumer-router"
        if hops <= 2: return "direct-isp"
        if hops >= 6: return "deep-infra"
        return "unknown"

    @classmethod
    def full_recon(cls, ssid, bssid):
        t0 = time.time()
        dns = cls.dns_servers(); trace = cls.route_trace()
        isp = cls.identify_isp() if trace["ok"] else "unknown"
        neighbors = cls.neighbors_estimate()
        return {"ssid": ssid, "bssid": bssid, "dns_servers": dns["servers"],
                "dns_type": dns["type"], "route_hops": trace["hops"], "depth": trace["depth"],
                "isp": isp, "neighbors_estimate": neighbors,
                "infra_type": cls._classify(ssid, dns["servers"], trace["depth"]),
                "recon_at": time.time(), "duration_ms": round((time.time()-t0)*1000, 1)}
