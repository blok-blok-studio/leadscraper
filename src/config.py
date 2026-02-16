"""Configuration loader for the lead scraper."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"


def load_config(config_path: str = None) -> dict:
    """Load YAML config file, merging with defaults."""
    default_path = CONFIG_DIR / "default.yaml"

    with open(default_path) as f:
        config = yaml.safe_load(f)

    if config_path:
        with open(config_path) as f:
            overrides = yaml.safe_load(f)
        _deep_merge(config, overrides)

    return config


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base dict."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


# Scraper settings from env
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT_REQUESTS", "5"))
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY_SECONDS", "2"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
PROXY_URL = os.getenv("PROXY_URL")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "logs/scraper.log")
