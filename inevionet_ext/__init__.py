"""🍄 InevioNet Ext — обёртка над корневыми модулями.

Цель P9.5: сделать `final_features`, `seed_server`, `tcp_probe`
частью пакета, чтобы PyInstaller и pip install работали.

Ре-экспортирует всё из корневых модулей.
"""
import sys
import os
from pathlib import Path

# Добавляем корень проекта в sys.path, чтобы найти final_features
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Ре-экспорт final_features
try:
    import final_features as _ff
    # Публичный API
    get_public_ip = _ff.get_public_ip
    try_upnp_port_forward = _ff.try_upnp_port_forward
    detect_local_subnet_ip = _ff.detect_local_subnet_ip
    detect_local_subnet = _ff.detect_local_subnet
    ping_sweep = _ff.ping_sweep
    get_last_sweep_info = _ff.get_last_sweep_info
    scan_arp_pivot = _ff.scan_arp_pivot
    identify_vendor = _ff.identify_vendor
    classify_device = _ff.classify_device
    SporeRelay = _ff.SporeRelay
    tracker_loop = _ff.tracker_loop
    pivoting_loop = _ff.pivoting_loop
    attach_routes = _ff.attach_routes
    FINAL_FEATURES_AVAILABLE = True
except ImportError as e:
    FINAL_FEATURES_AVAILABLE = False
    _IMPORT_ERROR = str(e)

__version__ = "1.0.0"