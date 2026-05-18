"""
logging_config.py — Centralised logging setup for the trading bot.

Configures:
  - A RotatingFileHandler writing DEBUG+ to logs/trading_bot.log
    (max 5 MB per file, 3 backup files kept)
  - A StreamHandler writing INFO+ to the console

Call ``get_logger(name)`` from any module to obtain a properly
configured :class:`logging.Logger` instance.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "trading_bot.log")
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_BACKUP_COUNT = 3
_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Guard so that handlers are only attached once per process lifetime
_configured = False


def _ensure_log_dir() -> None:
    """Create the logs/ directory if it does not already exist."""
    os.makedirs(_LOG_DIR, exist_ok=True)


def _configure_root_logger() -> None:
    """
    Attach file and stream handlers to the root logger exactly once.

    Subsequent calls are no-ops, making the function safe to call from
    multiple modules during import.
    """
    global _configured
    if _configured:
        return

    _ensure_log_dir()

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # --- Rotating file handler (DEBUG and above) ---
    file_handler = RotatingFileHandler(
        _LOG_FILE,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # --- Stream / console handler (INFO and above) ---
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # lowest level wins; handlers filter further
    root.addHandler(file_handler)
    root.addHandler(stream_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a named :class:`logging.Logger` configured for the trading bot.

    The root logger is set up on the first call; subsequent calls simply
    retrieve the named child logger from the already-configured hierarchy.

    Parameters
    ----------
    name:
        Typically ``__name__`` of the calling module, e.g. ``"bot.client"``.

    Returns
    -------
    logging.Logger
        A logger inheriting handlers from the root logger.

    Example
    -------
    >>> from bot.logging_config import get_logger
    >>> logger = get_logger(__name__)
    >>> logger.info("Bot started")
    """
    _configure_root_logger()
    return logging.getLogger(name)
