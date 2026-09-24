import sys
import io

# 🛡️ FIX: Принудительно переводим stdout/stderr в UTF-8 для Windows, 
# чтобы logging не падал при выводе эмодзи (🍄, 🌱) в консоль.
if sys.platform == 'win32':
    try:
        # Для Python 3.7+
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        # Fallback для старых версий
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
"""InevioNet Logging."""
import sys
import logging
import logging.handlers
from datetime import datetime
from typing import Dict, Optional
from .constants import DataPaths, IS_WINDOWS

class Colors:
    """ANSI color codes with safe stdout checking."""
    SUPPORTED = False
    if sys.stdout is not None:
        try:
            SUPPORTED = (not IS_WINDOWS or sys.stdout.isatty())
        except (AttributeError, OSError):
            SUPPORTED = False
    
    RESET = "\033[0m" if SUPPORTED else ""
    RED = "\033[31m" if SUPPORTED else ""
    GREEN = "\033[32m" if SUPPORTED else ""
    YELLOW = "\033[33m" if SUPPORTED else ""
    CYAN = "\033[36m" if SUPPORTED else ""
    MAGENTA = "\033[35m" if SUPPORTED else ""
    DIM = "\033[2m" if SUPPORTED else ""

class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': Colors.DIM,
        'INFO': Colors.GREEN,
        'WARNING': Colors.YELLOW,
        'ERROR': Colors.RED,
        'CRITICAL': Colors.MAGENTA,
    }
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, Colors.RESET)
        record.levelname = f"{color}{record.levelname}{Colors.RESET}"
        return super().format(record)

def setup_logger(name="inevionet", level=logging.INFO):
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # Console handler
    console = logging.StreamHandler()
    console.setLevel(level)
    formatter = ColoredFormatter(
        '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S'
    )
    console.setFormatter(formatter)
    logger.addHandler(console)
    
    # File handler
    try:
        log_file = DataPaths.get_logs_dir() / f"{name}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception:
        pass
    
    return logger

def get_logger(name: str) -> logging.Logger:
    full_name = f"inevionet.{name}" if not name.startswith("inevionet") else name
    return setup_logger(full_name)

# Global flag to prevent re-initialization
_INITIALIZED = False

def init_default_logging(level="INFO"):
    """Initialize default logging for the entire application."""
    global _INITIALIZED
    if _INITIALIZED:
        return
    setup_logger(name="inevionet", level=logging.INFO)
    _INITIALIZED = True


