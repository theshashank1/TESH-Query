"""
Configuration Utilities for TESH-Query

Provides functions for retrieving, saving, and validating configuration.

All configuration is stored under ``~/.teshq/``:
- Secrets  (DATABASE_URL, GEMINI_API_KEY) → ``~/.teshq/.teshq.env``  (mode 0600)
- Settings (model name, paths, etc.)       → ``~/.teshq/config.yaml``

Environment variables always take the highest priority.

Functions:
- get_config(): Retrieve merged configuration.
- save_config(): Persist configuration (secrets → .teshq.env, rest → config.yaml).
- get_database_url(): Get the database connection URL.
- get_gemini_config(): Get Gemini API key and model name.
- get_paths(): Get output and file storage paths.
- is_configured(): Check if essential configuration is present.
- print_config_debug(): Print detailed configuration status for debugging.
"""

import os
from typing import Dict, Optional, Tuple

from teshq.config.secrets import SECRET_KEYS, load_secrets, save_secrets
from teshq.config.settings import DEFAULT_SETTINGS, SETTINGS_KEYS, load_settings, save_settings

# Public constant: default model name (kept for backward compatibility)
DEFAULT_GEMINI_MODEL = DEFAULT_SETTINGS["GEMINI_MODEL_NAME"]

# All configuration keys (union of secrets and settings)
CONFIG_KEYS = list(SECRET_KEYS) + list(SETTINGS_KEYS)


def get_config() -> Dict[str, Optional[str]]:
    """
    Return merged configuration with the following priority (highest first):

    1. Environment variables
    2. ``~/.teshq/.teshq.env`` (secrets)
    3. ``~/.teshq/config.yaml`` (non-secret settings)
    """
    config: Dict[str, Optional[str]] = {}

    # Load non-secret settings (lowest file priority)
    config.update(load_settings())

    # Load secrets (override settings if key names overlap — they don't, by design)
    config.update(load_secrets())

    # Environment variables win over everything
    for key in CONFIG_KEYS:
        env_val = os.environ.get(key)
        if env_val:
            config[key] = env_val

    return config


def get_config_with_source() -> Tuple[Dict[str, Optional[str]], Dict[str, str]]:
    """Return (config_dict, sources_dict) so callers can show where each value came from."""
    from teshq.config.paths import CONFIG_FILE, SECRETS_FILE
    from teshq.config.secrets import _read_env_file
    from teshq.config.settings import _load_yaml

    config: Dict[str, Optional[str]] = {}
    sources: Dict[str, str] = {}

    # Non-secret settings from YAML
    yaml_data = _load_yaml(CONFIG_FILE)
    for key in SETTINGS_KEYS:
        if key in yaml_data:
            config[key] = yaml_data[key]
            sources[key] = f"~/.teshq/config.yaml"

    # Secrets from .teshq.env
    env_data = _read_env_file(SECRETS_FILE)
    for key in SECRET_KEYS:
        if key in env_data:
            config[key] = env_data[key]
            sources[key] = f"~/.teshq/.teshq.env"

    # Environment variables (highest priority)
    for key in CONFIG_KEYS:
        env_val = os.environ.get(key)
        if env_val:
            config[key] = env_val
            sources[key] = "environment"

    # Only return keys that have values
    config = {k: v for k, v in config.items() if v}
    sources = {k: v for k, v in sources.items() if k in config}

    return config, sources


def save_config(data: Dict[str, Optional[str]]) -> bool:
    """
    Save configuration to ``~/.teshq/``.

    - Secret keys (DATABASE_URL, GEMINI_API_KEY) → ``~/.teshq/.teshq.env``
    - Non-secret keys                             → ``~/.teshq/config.yaml``

    Args:
        data: Mapping of config key → value.  Pass ``None`` to remove a key.

    Returns:
        bool: True if all writes succeeded.
    """
    secrets_data = {k: v for k, v in data.items() if k in SECRET_KEYS}
    settings_data = {k: v for k, v in data.items() if k in SETTINGS_KEYS}

    ok = True
    if secrets_data:
        ok = save_secrets(secrets_data) and ok
    if settings_data:
        ok = save_settings(settings_data) and ok
    return ok


def get_database_url() -> Optional[str]:
    """Get database URL."""
    return get_config().get("DATABASE_URL")


def get_gemini_config() -> Tuple[Optional[str], str]:
    """Get Gemini API key and model name."""
    config = get_config()
    api_key = config.get("GEMINI_API_KEY")
    model = config.get("GEMINI_MODEL_NAME", DEFAULT_GEMINI_MODEL)
    return api_key, model


def get_paths() -> Tuple[str, str]:
    """Get output and file store paths."""
    config = get_config()
    output_path = config.get("OUTPUT_PATH", DEFAULT_SETTINGS["OUTPUT_PATH"])
    file_store_path = config.get("FILE_STORE_PATH", DEFAULT_SETTINGS["FILE_STORE_PATH"])
    return output_path, file_store_path


def is_configured() -> bool:
    """Return True when both DATABASE_URL and GEMINI_API_KEY are set."""
    config = get_config()
    return bool(config.get("DATABASE_URL") and config.get("GEMINI_API_KEY"))


def print_config_debug():
    """Print configuration debug information."""
    config, sources = get_config_with_source()

    print("🔍 Configuration Status")
    print("=" * 40)

    for key in CONFIG_KEYS:
        value = config.get(key)
        source = sources.get(key, "not_found")

        # Mask sensitive values
        display_value = value
        if key == "GEMINI_API_KEY" and value:
            display_value = "********"
        elif key == "DATABASE_URL" and value:
            try:
                from sqlalchemy.engine.url import make_url

                url_obj = make_url(value)
                display_value = str(url_obj._replace(password="********")) if url_obj.password else value
            except ImportError:
                display_value = "configured (masked)"

        status_str = "✅ SET" if value else "❌ NOT SET"
        print(f"{key}: {status_str} (from {source})")
        if display_value and value:
            print(f"  Value: {display_value}")
        print()


if __name__ == "__main__":
    print("Get all config:", get_config())
    print("Get config with source:", get_config_with_source())
    print("Get DB URL:", get_database_url())
    print("Get Gemini config:", get_gemini_config())
    print("Get paths:", get_paths())
    print("Is configured:", is_configured())
    print_config_debug()
