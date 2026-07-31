"""
config.py — Loads config.yaml and resolves ${ENV_VAR} placeholders from environment.
"""
import os
import re
import yaml
import copy
from pathlib import Path
from functools import lru_cache
from typing import Any

CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", "/config/config.yaml"))


def _expand_env(value: str) -> str:
    """Replace ${VAR_NAME} with the corresponding environment variable."""
    def replacer(match):
        var_name = match.group(1)
        val = os.environ.get(var_name)
        if val is None:
            raise RuntimeError(
                f"Environment variable '{var_name}' referenced in config.yaml is not set. "
                f"Check your .env file."
            )
        return val
    return re.sub(r"\$\{([^}]+)\}", replacer, value)


def _expand_nested(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _expand_nested(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_expand_nested(i) for i in obj]
    elif isinstance(obj, str):
        return _expand_env(obj)
    return obj


@lru_cache(maxsize=1)
def _load_raw() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def get_config() -> dict:
    """Return config with all ${ENV_VAR} placeholders resolved."""
    return _expand_nested(_load_raw())


def reload_config() -> dict:
    """Force reload from disk (clears lru_cache)."""
    _load_raw.cache_clear()
    return get_config()


def get_cameras() -> list[dict]:
    return get_config()["cameras"]


def get_recording_config() -> dict:
    return get_config()["recording"]


def get_go2rtc_config() -> dict:
    return get_config()["go2rtc"]


def get_app_config() -> dict:
    return get_config()["app"]
