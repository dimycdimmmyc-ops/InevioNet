import sys
import io

# 🛡️ FIX: Принудительно переводим stdout/stderr в UTF-8 для Windows, 
# чтобы logging не падал при выводе эмодзи (🍄, 🌱) в консоль.
if sys.platform == 'win32':
    try:
        # Для Python 3.7+
        if sys.stdout is not None and hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if sys.stderr is not None and hasattr(sys.stderr, 'reconfigure'): sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        # Fallback для старых версий
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
"""InevioNet - Guaranteed Delivery Protocol."""
__version__ = "1.0.0"
__author__ = "InevioNet Team"
__license__ = "MIT"

from .core.constants import (
    DataPaths, InevioMode, ProtocolType, PacketPriority, PacketState,
    PROTOCOLS, DEFAULT_CONFIG, get_mode_config, is_root)
from .core.crypto import InevioCrypto, KeyPair
from .core.packet import GDPPacket, create_packet, create_text_packet
from .core.logger import get_logger, setup_logger, init_default_logging
from .core.exceptions import (
    InevioException, CryptoError, NetworkError,
    SteganographyError, DeliveryError, ConfigurationError)

from .network.transport import UniversalTransport, TransportResult
from .steganography.engine import SteganographyEngine
from .evolution.engine import EvolutionEngine
from .symbiotic.ecosystem import SymbioticEcosystem
from .mycelium.engine import MyceliumEngine
from .ai.selector import ProtocolSelector
from .ai.recursion import WeightedRecursion

from .orchestrator import InevioNet

from .simple import send, receive, run, stop, quick


__all__ = [
    "__version__",
    # Core
    "InevioCrypto", "KeyPair", "GDPPacket", "create_packet", "create_text_packet",
    "get_logger", "setup_logger", "init_default_logging",
    "DataPaths", "InevioMode", "ProtocolType", "PacketPriority", "PacketState",
    "PROTOCOLS", "DEFAULT_CONFIG", "get_mode_config", "is_root",
    # Exceptions
    "InevioException", "CryptoError", "NetworkError",
    "SteganographyError", "DeliveryError", "ConfigurationError",
    # Network
    "UniversalTransport", "TransportResult",
    # Steganography
    "SteganographyEngine",
    # Evolution
    "EvolutionEngine",
    # Symbiotic
    "SymbioticEcosystem",
    # Mycelium
    "MyceliumEngine",
    # AI
    "ProtocolSelector", "WeightedRecursion",
    # Main class
    "InevioNet",
    # Simple API
    "send", "receive", "run", "stop", "quick",
]


def show_banner():
    print(r"""
+===============================================================+
|  INEVIONET v1.0.0                                             |
|  Guaranteed Delivery Protocol                                 |
|  "Сети видят выбор, но выбора нет. Пакет всегда доставляется." |
+===============================================================+
""")

# Identity (device identification)
from .identity import (
    DeviceID, DeviceType, DeviceRole, DeviceIDGenerator,
    DeviceIdentity, DeviceRegistry, DeviceRecord,
    DiscoveryEngine, DeviceAnnouncement, DiscoveryMethod,
    TrustEngine, TrustRecord, TrustLevel,
    DeviceFingerprint, PresenceManager, PresenceRecord, PresenceStatus)

__all__.extend([
    "DeviceID", "DeviceType", "DeviceRole", "DeviceIDGenerator",
    "DeviceIdentity", "DeviceRegistry", "DeviceRecord",
    "DiscoveryEngine", "DeviceAnnouncement", "DiscoveryMethod",
    "TrustEngine", "TrustRecord", "TrustLevel",
    "DeviceFingerprint", "PresenceManager", "PresenceRecord", "PresenceStatus",
])

# Industrial protocols
from .industrial import (
    IndustrialProtocol, IndustrialPacket,
    ModbusTCP, ModbusRTU, OPCUA, MQTTClient, DNP3)

# Capsule
from .capsule import (
    InevioCapsule, embed_inevionet, quick_send, quick_receive)

__all__.extend([
    "IndustrialProtocol", "IndustrialPacket",
    "ModbusTCP", "ModbusRTU", "OPCUA", "MQTTClient", "DNP3",
    "InevioCapsule", "embed_inevionet", "quick_send", "quick_receive",
])

