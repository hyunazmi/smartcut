from __future__ import annotations

import logging
import os
import sys

SUCCESS = 25
LOGGER_NAME = "snipy"
logging.addLevelName(SUCCESS, "SUCCESS")
_RESET = "\x1b[0m"
_BOLD = "\x1b[1m"
_COLORS = {
    logging.INFO: "\x1b[36m",
    SUCCESS: "\x1b[32m",
    logging.WARNING: "\x1b[33m",
    logging.ERROR: "\x1b[31m",
}


def _supports_color() -> bool:
    return sys.stderr.isatty() and "NO_COLOR" not in os.environ


def format_line(level: int, message: str) -> str:
    tag = f"[{logging.getLevelName(level)}]"
    if _supports_color():
        tag = f"{_BOLD}{_COLORS.get(level, '')}{tag}{_RESET}"
    return f"{tag} {message}"


class _LogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return format_line(record.levelno, record.getMessage())


def _enable_windows_ansi() -> None:
    if _supports_color() and os.name == "nt":
        os.system("")


def configure_logging() -> None:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        _enable_windows_ansi()
        handler = logging.StreamHandler()
        handler.setFormatter(_LogFormatter())
        logger.addHandler(handler)
