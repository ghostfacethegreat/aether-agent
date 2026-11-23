import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from aether.utils import redact


class RedactingFilter(logging.Filter):
    def filter(self, record):
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


_LOGGERS = {}


def get_logger(name="aether", config=None) -> logging.Logger:
    if name in _LOGGERS:
        return _LOGGERS[name]
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    console.addFilter(RedactingFilter())
    level = str((config or {}).get("level", "INFO")).upper() if config else "INFO"
    console.setLevel(getattr(logging, level, logging.INFO))
    logger.addHandler(console)
    if config and config.get("file", True):
        from aether.home import aether_home

        path = Path(aether_home()) / "logs" / "aether.log"
        handler = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=2, encoding="utf-8")
        handler.setFormatter(formatter)
        handler.addFilter(RedactingFilter())
        logger.addHandler(handler)
    _LOGGERS[name] = logger
    return logger


def set_level(level: str) -> None:
    resolved = getattr(logging, str(level).upper(), logging.INFO)
    for logger in _LOGGERS.values():
        for handler in logger.handlers:
            if not isinstance(handler, RotatingFileHandler):
                handler.setLevel(resolved)
