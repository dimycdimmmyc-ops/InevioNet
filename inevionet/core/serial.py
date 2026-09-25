"""InevioNet Serial - уникальный идентификатор узла.

P103: Серийник генерится при первом запуске EXE.
6 цифр (1 млн вариантов). Сохраняется в serial.txt.
"""
import os
import random
import re
from pathlib import Path
from typing import Optional

from .logger import get_logger

logger = get_logger("inevionet.core.serial")


SERIAL_PATTERN = re.compile(r"^SN-\d{6}$")


def generate_serial() -> str:
    """Сгенерировать уникальный serial (6 цифр)."""
    n = random.randint(1, 999999)
    return "SN-%06d" % n


def is_valid_serial(s: str) -> bool:
    """Проверить валидность serial."""
    if not s or not isinstance(s, str):
        return False
    return bool(SERIAL_PATTERN.match(s.strip()))


def get_serial_file(data_home: str = None) -> Path:
    """Путь к serial.txt (per-port, P116)."""
    if data_home is None:
        data_home = os.environ.get("INEVIO_DATA_DIR") or os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")),
            "InevioNet", "data")
    port = os.environ.get("INEVIO_PORT", "8080")
    return Path(data_home) / ("serial_%s.txt" % port)


def get_or_create_serial(data_home: str = None) -> str:
    """Получить или создать serial."""
    path = get_serial_file(data_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            s = path.read_text(encoding="utf-8").strip()
            if is_valid_serial(s):
                logger.info("[Serial] loaded: %s", s)
                return s
            logger.warning("[Serial] invalid format: %s — regenerating", s)
        except Exception as e:
            logger.warning("[Serial] read error: %s", e)
    s = generate_serial()
    try:
        path.write_text(s, encoding="utf-8")
        logger.info("[Serial] created: %s (saved to %s)", s, path)
    except Exception as e:
        logger.error("[Serial] save error: %s", e)
    return s


def get_current_serial() -> str:
    """Получить текущий serial (глобально)."""
    return get_or_create_serial()
