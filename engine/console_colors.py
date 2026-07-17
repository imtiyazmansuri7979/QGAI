"""
console_colors.py - ANSI color helpers for QGAI console windows.

File logs stay plain; only interactive console output is colored.
"""
import logging
import os
import re
import sys
from pathlib import Path

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"

RESET = "\033[0m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"
BOLD = "\033[1m"
ORANGE = "\033[38;2;255;152;0m"

_COLOR_ENABLED = None


def enable_console_color():
    """Enable ANSI color support in Windows console, if available."""
    global _COLOR_ENABLED
    if _COLOR_ENABLED is not None:
        return _COLOR_ENABLED

    if os.environ.get("NO_COLOR") or os.environ.get("QGAI_NO_COLOR"):
        _COLOR_ENABLED = False
        return False

    if not (sys.stdout.isatty() or sys.stderr.isatty()):
        _COLOR_ENABLED = False
        return False

    if os.name != "nt":
        _COLOR_ENABLED = True
        return True

    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        enabled = False
        for handle_id in (-11, -12):  # STD_OUTPUT_HANDLE, STD_ERROR_HANDLE
            handle = kernel32.GetStdHandle(handle_id)
            mode = ctypes.c_uint()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                enabled = bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004)) or enabled
        _COLOR_ENABLED = enabled
        return enabled
    except Exception:
        _COLOR_ENABLED = False
        return False


def paint(text, color):
    if not enable_console_color() or not color:
        return str(text)
    return f"{color}{text}{RESET}"


class QGAIColorFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.DEBUG: DIM,
        logging.INFO: WHITE,
        logging.WARNING: YELLOW + BOLD,
        logging.ERROR: RED + BOLD,
        logging.CRITICAL: RED + BOLD,
    }
    LEVEL_EMOJI = {
        logging.DEBUG: "🐛",
        logging.INFO: "ℹ️",
        logging.WARNING: "⚠️",
        logging.ERROR: "❌",
        logging.CRITICAL: "🔥",
    }

    KEYWORD_COLORS = [
        (r"\b(ERROR|FAILED|failed|fail|TIMEOUT|halt|crashed)\b", RED + BOLD),
        (r"\b(WARNING|SKIP|watchdog|gap|retrain|reload|TASK)\b", YELLOW + BOLD),
        (r"\b(OK|done|fresh|started|running|stopped|saved|connected|loaded|complete|live|ALIVE)\b", GREEN + BOLD),
        (r"\b(Bridge|Scheduler|Dashboard|model|MT5|NY session|Broker)\b", CYAN + BOLD),
        (r"\b(Primary|Secondary|manual|multi)\b", MAGENTA + BOLD),
        (r"\b(XAUUSD(?:\.pc)?|M15|H1|H4)\b", BLUE + BOLD),
        (r"\bTrending\b", GREEN + BOLD),
        (r"\bVolatile\b", ORANGE + BOLD),
        (r"\bRanging\b", RED + BOLD),
        (r"\bNew bar\b", MAGENTA + BOLD),
        (r"\bheartbeat\b", CYAN + BOLD),
        (r"\b(price|last bar)\b", DIM),
        (r"(?<!^)\b\d{1,2}:\d{2}(?::\d{2})?\b", CYAN),
        (r"[$][0-9,]+(?:\.[0-9]+)?", GREEN + BOLD),
        (r"\b[+-]?[0-9]+(?:\.[0-9]+)?R\b", YELLOW + BOLD),
        (r"(?<![\d.$,])\b\d{3,5}\.\d{1,2}\b(?!\s*R\b)(?!%)", CYAN + BOLD),
    ]

    def format(self, record):
        if not enable_console_color():
            return super().format(record)

        record_copy = logging.makeLogRecord(record.__dict__.copy())
        _emoji = self.LEVEL_EMOJI.get(record.levelno, "")
        record_copy.levelname = paint(f"{_emoji} {record.levelname}" if _emoji else record.levelname,
                                       self.LEVEL_COLORS.get(record.levelno, ""))
        record_copy.msg = self._color_message(record.getMessage())
        record_copy.args = ()

        line = super().format(record_copy)
        return re.sub(
            r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})",
            lambda m: paint(m.group(1), DIM),
            line,
        )

    @classmethod
    def _color_message(cls, message):
        colored = message
        for pattern, color in cls.KEYWORD_COLORS:
            colored = re.sub(pattern, lambda m: paint(m.group(0), color), colored, flags=re.IGNORECASE)
        return colored


def configure_color_logger(name, log_file, level=logging.INFO, fmt=LOG_FORMAT):
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(QGAIColorFormatter(fmt))

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(fmt))

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger
