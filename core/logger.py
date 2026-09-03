"""Centralized logging for JARVIS.

Every module should obtain its logger with ``get_logger(__name__)`` instead
of calling ``print()``. This gives us:

- A single place to control verbosity (via ``config.LOG_LEVEL`` or the
  ``JARVIS_LOG_LEVEL`` environment variable).
- A rotating log file under ``data/logs/jarvis.log`` so issues that happen
  during real usage (voice recognition glitches, Ollama timeouts, Windows
  API failures, ...) can be inspected after the fact instead of only
  flashing by in a console window that most users never look at.
- Consistent, timestamped, leveled output on stdout as well.

The setup is done lazily and only once per process, so importing this
module from many places (as intended) is cheap and side-effect free after
the first call.
"""

import logging
import logging.handlers
import sys
import threading

try:
    from config import DATA_DIR, LOG_LEVEL, LOG_TO_FILE
except Exception:  # pragma: no cover - config should always be importable
    from pathlib import Path

    DATA_DIR = Path(__file__).resolve().parent.parent / "data"
    LOG_LEVEL = "INFO"
    LOG_TO_FILE = True


_LOCK = threading.Lock()
_CONFIGURED = False
_ROOT_NAME = "jarvis"


def _level_from_name(name):
    if isinstance(name, int):
        return name
    return getattr(logging, str(name).upper(), logging.INFO)


def _configure_root():
    """Attach handlers to the ``jarvis`` root logger exactly once."""

    global _CONFIGURED

    if _CONFIGURED:
        return

    with _LOCK:
        if _CONFIGURED:
            return

        root = logging.getLogger(_ROOT_NAME)
        root.setLevel(_level_from_name(LOG_LEVEL))
        root.propagate = False

        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | %(name)-24s | %(message)s",
            datefmt="%H:%M:%S",
        )

        console = logging.StreamHandler(stream=sys.stdout)
        console.setFormatter(formatter)
        root.addHandler(console)

        if LOG_TO_FILE:
            try:
                log_dir = DATA_DIR / "logs"
                log_dir.mkdir(parents=True, exist_ok=True)

                file_handler = logging.handlers.RotatingFileHandler(
                    filename=str(log_dir / "jarvis.log"),
                    maxBytes=2 * 1024 * 1024,
                    backupCount=5,
                    encoding="utf-8",
                )
                file_handler.setFormatter(formatter)
                root.addHandler(file_handler)
            except Exception:
                # Logging must never crash the assistant. If we cannot
                # write to disk (read-only install, permissions, ...) we
                # simply keep console-only logging.
                root.addHandler(logging.NullHandler())

        _CONFIGURED = True


def get_logger(name="jarvis"):
    """Return a module-scoped logger namespaced under ``jarvis.*``.

    Usage::

        from core.logger import get_logger
        logger = get_logger(__name__)
        logger.info("something happened")
    """

    _configure_root()

    if name in (None, "", "__main__"):
        return logging.getLogger(_ROOT_NAME)

    return logging.getLogger(f"{_ROOT_NAME}.{name}")


def set_level(level):
    """Change the effective log level at runtime (e.g. from a settings UI)."""

    _configure_root()
    logging.getLogger(_ROOT_NAME).setLevel(_level_from_name(level))
