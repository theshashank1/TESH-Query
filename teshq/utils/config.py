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
    Merge configuration values from settings, secrets, and environment with environment variables taking precedence.
    
    For each known configuration key the returned mapping contains the highest-priority available value: environment variables override secrets (~/.teshq/.teshq.env), which override non-secret settings (~/.teshq/config.yaml).
    
    Returns:
        Dict[str, Optional[str]]: Mapping of configuration keys to their values (strings) or None when unset.
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
    """
    Merge configuration values from settings, secrets, and environment and report the origin of each value.
    
    Loads non-secret settings from ~/.teshq/config.yaml, then overlays secrets from ~/.teshq/.teshq.env, and finally overlays environment variables (highest priority). Only keys with non-empty values are included in the returned mappings.
    
    Returns:
        Tuple[Dict[str, Optional[str]], Dict[str, str]]: 
            - config: Mapping of configuration keys to their resolved values.
            - sources: Mapping of configuration keys to a short source identifier: "environment", "~/.teshq/.teshq.env", or "~/.teshq/config.yaml".
    """
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
    Save configuration entries to the user's TESH-Query config directory (~/.teshq/).
    
    Secret keys (DATABASE_URL, GEMINI_API_KEY) are written to ~/.teshq/.teshq.env; non-secret settings are written to ~/.teshq/config.yaml.
    
    Parameters:
        data (Dict[str, Optional[str]]): Mapping of configuration keys to values. Use None to remove a key.
    
    Returns:
        `true` if all writes succeeded, `false` otherwise.
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
    """
    Retrieve the configured database connection URL.
    
    Returns:
        The `DATABASE_URL` value from the merged configuration, or `None` if it is not set.
    """
    return get_config().get("DATABASE_URL")


def get_gemini_config() -> Tuple[Optional[str], str]:
    """
    Retrieve the Gemini API key and the Gemini model name from the merged configuration.
    
    Returns:
        tuple: (api_key, model_name)
            api_key (str | None): The Gemini API key if configured, otherwise `None`.
            model_name (str): The Gemini model name from configuration or `DEFAULT_GEMINI_MODEL` when not set.
    """
    config = get_config()
    api_key = config.get("GEMINI_API_KEY")
    model = config.get("GEMINI_MODEL_NAME", DEFAULT_GEMINI_MODEL)
    return api_key, model


def get_paths() -> Tuple[str, str]:
    """
    Retrieve the configured output and file storage paths.
    
    Returns:
        A tuple (output_path, file_store_path) where each value is taken from the merged configuration if present; otherwise the corresponding default from DEFAULT_SETTINGS["OUTPUT_PATH"] and DEFAULT_SETTINGS["FILE_STORE_PATH"] is returned.
    """
    config = get_config()
    output_path = config.get("OUTPUT_PATH", DEFAULT_SETTINGS["OUTPUT_PATH"])
    file_store_path = config.get("FILE_STORE_PATH", DEFAULT_SETTINGS["FILE_STORE_PATH"])
    return output_path, file_store_path


def is_configured() -> bool:
    """
    Determine whether the required configuration values for operation are present.
    
    Returns:
        `true` if both `DATABASE_URL` and `GEMINI_API_KEY` are set, `false` otherwise.
    """
    config = get_config()
    return bool(config.get("DATABASE_URL") and config.get("GEMINI_API_KEY"))


def print_config_debug():
    """
    Print a human-readable debug summary of the current configuration and the source of each value.
    
    For each key in CONFIG_KEYS this prints whether the key is set, the recorded source (environment, secrets file, settings file, or not found), and a masked or partial value when present. GEMINI_API_KEY is fully masked. For DATABASE_URL the password component is masked if URL parsing via SQLAlchemy is available; otherwise the value is shown as "configured (masked)".
    """
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
