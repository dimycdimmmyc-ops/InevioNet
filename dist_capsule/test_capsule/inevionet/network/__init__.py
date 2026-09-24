"""InevioNet Network."""
from .tcp import TCPClient, TCPServer
from .udp import UDPClient, UDPServer, UDPHolePuncher, stun_get_public_ip
from .dns import DNSClient, DNSResponse, DNSType, DNSClass
from .http import HTTPClient, HTTPResponse
from .icmp import ICMPClient, ICMPResult
from .rf_scanner import RFScanner, RFSignal, RFSignalType, ScanResult

try:
    from .websocket import WSClient, WSServer, WEBSOCKETS_AVAILABLE
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    WSClient = None
    WSServer = None

from .transport import UniversalTransport, TransportResult

__all__ = [
    "TCPClient", "TCPServer",
    "UDPClient", "UDPServer", "UDPHolePuncher", "stun_get_public_ip",
    "DNSClient", "DNSResponse", "DNSType", "DNSClass",
    "HTTPClient", "HTTPResponse",
    "ICMPClient", "ICMPResult",
    "RFScanner", "RFSignal", "RFSignalType", "ScanResult",
    "WSClient", "WSServer", "WEBSOCKETS_AVAILABLE",
    "UniversalTransport", "TransportResult",
]

# === P8: BLE / LTE / GPS scanners ===
try:
    from .ble_scanner import scan_ble
except ImportError:
    scan_ble = None

try:
    from .lte_scanner import scan_lte
except ImportError:
    scan_lte = None

try:
    from .gps_scanner import scan_gps
except ImportError:
    scan_gps = None

try:
    from .hole_puncher import HolePuncher
except ImportError:
    HolePuncher = None

try:
    from .auto_bootstrap import AutoBootstrap
except ImportError:
    AutoBootstrap = None