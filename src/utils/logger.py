"""Logging configuration with rich console output."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from rich.logging import RichHandler

from src.config import LOG_LEVEL, LOG_FILE


def setup_logging():
    """Configure logging with console (rich) and file handlers."""
    log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)

    # Ensure log directory exists
    log_path = Path(LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Root logger
    root = logging.getLogger()
    root.setLevel(log_level)

    # Clear existing handlers
    root.handlers.clear()

    # Rich console handler
    console_handler = RichHandler(
        level=log_level,
        rich_tracebacks=True,
        show_time=True,
        show_path=False,
    )
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(console_handler)

    # File handler
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(file_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    return root
