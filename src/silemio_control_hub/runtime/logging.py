"""Rotating product log used by the real-time controller engine."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import default_data_dir


LOGGER_NAME = "silemio_control_hub"


def default_log_path() -> Path:
    return default_data_dir() / "controller-studio.log"


def configure_runtime_logging(level: str = "INFO", path: Path | None = None) -> Path:
    """Configure one reusable UTF-8 rotating file handler for the product."""

    log_path = path or default_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(LOGGER_NAME)
    resolved_level = getattr(logging, str(level).upper(), logging.INFO)
    logger.setLevel(resolved_level)
    logger.propagate = False

    wanted = log_path.resolve()
    existing: RotatingFileHandler | None = None
    for handler in tuple(logger.handlers):
        if not getattr(handler, "_silemio_runtime_handler", False):
            continue
        current = Path(getattr(handler, "baseFilename", "")).resolve()
        if current == wanted:
            existing = handler
            continue
        logger.removeHandler(handler)
        handler.close()

    if existing is None:
        existing = RotatingFileHandler(
            log_path,
            maxBytes=2_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        existing._silemio_runtime_handler = True  # type: ignore[attr-defined]
        existing.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        )
        logger.addHandler(existing)
    existing.setLevel(resolved_level)
    return log_path
