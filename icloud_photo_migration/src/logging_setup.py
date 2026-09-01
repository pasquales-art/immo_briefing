"""Logging: gleichzeitig Konsole + rotierende Logdatei."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False


def setup_logging(logs_dir: Path, level: int = logging.INFO) -> logging.Logger:
    """Initialisiert Root-Logger einmalig. Gibt Projekt-Logger zurück."""
    global _CONFIGURED
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("photo_migration")

    if _CONFIGURED:
        return logger

    logger.setLevel(level)
    logger.propagate = False
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    file_handler = RotatingFileHandler(
        logs_dir / "migration.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    _CONFIGURED = True
    logger.info("Logging initialisiert -> %s", logs_dir / "migration.log")
    return logger


def get_logger(name: str = "photo_migration") -> logging.Logger:
    return logging.getLogger(name)
