"""
Configuration Utilities for TESH-Query (v2 compatibility shim)

All functions delegate to teshq.config.settings.Settings (pydantic-settings).
The public API is preserved for backward compatibility with existing CLI code.

Functions:
- get_config()            → merged config as a plain dict
- save_config()           → persist config (secrets → .env, rest → yaml)
- get_database_url()      → DATABASE_URL value
- get_gemini_config()     → (api_key, model_name) tuple
- get_paths()             → (output_path, file_store_path) tuple
- is_configured()         → True if both secrets are set
- print_config_debug()    → human-readable debug summary
"""

import os
from typing import Dict, Optional, Tuple

from teshq.config.secrets import SECRET_KEYS, save_secrets
from teshq.config.settings import save_secret, save_setting, get_settings

# Settings constants (kept for backward compat)
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash-lite"
SETTINGS_KEYS = {"GEMINI_MODEL", "OUTPUT_PATH", "FILE_STORE_PATH"}
CONFIG_KEYS = list(SECRET_KEYS) + list(SETTINGS_KEYS)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_config() -> Dict[str, Optional[str]]:
    """Return merged configuration as a plain dict (env vars win)."""
    s = get_settings(reload=True)
    return {
        "DATABASE_URL": s.database_url or None,
        "GEMINI_API_KEY": s.gemini_api_key or None,
        "GEMINI_MODEL": s.gemini_model,
        "OUTPUT_PATH": str(s.output_path),
        "FILE_STORE_PATH": str(s.file_store_path),
        "TESHQ_NO_TELEMETRY": str(s.no_telemetry).lower(),
    }


def get_config_with_source() -> Tuple[Dict[str, Optional[str]], Dict[str, str]]:
    """Return (config, sources) — sources maps key → origin string."""
    from teshq.config.paths import CONFIG_FILE, SECRETS_FILE
    from teshq.config.secrets import _read_env_file

    config = get_config()
    sources: Dict[str, str] = {}

    # Check secrets file
    env_data = _read_env_file(SECRETS_FILE)
    for key in SECRET_KEYS:
        if key in env_data and env_data[key]:
            sources[key] = "~/.teshq/.teshq.env"

    # Check YAML
    try:
        import yaml
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
                yaml_data = yaml.safe_load(fh) or {}
            for key in yaml_data:
                if key not in sources:
                    sources[key] = "~/.teshq/config.yaml"
    except Exception:
        pass

    # Env vars win
    for key in CONFIG_KEYS:
        if os.environ.get(key):
            sources[key] = "environment"

    config = {k: v for k, v in config.items() if v}
    sources = {k: v for k, v in sources.items() if k in config}
    return config, sources


def save_config(data: Dict[str, Optional[str]]) -> bool:
    """Save config entries — secrets to .env, others to config.yaml."""
    ok = True
    for key, value in data.items():
        if value is None:
            continue
        if key in SECRET_KEYS:
            ok = save_secret(key, value) and ok
        else:
            ok = save_setting(key, value) and ok
    return ok


def get_database_url() -> Optional[str]:
    """Return the configured DATABASE_URL, or None if not set."""
    return get_settings().database_url or None


def get_gemini_config() -> Tuple[Optional[str], str]:
    """Return (api_key, model_name) from current settings."""
    s = get_settings()
    return (s.gemini_api_key or None), s.gemini_model


def get_paths() -> Tuple[str, str]:
    """Return (output_path, file_store_path) from current settings."""
    s = get_settings()
    return str(s.output_path), str(s.file_store_path)


def is_configured() -> bool:
    """Return True if DATABASE_URL and GEMINI_API_KEY are both set."""
    return get_settings().is_configured


def print_config_debug() -> None:
    """Print a human-readable debug summary of the current configuration."""
    config, sources = get_config_with_source()
    s = get_settings()

    print("🔍 Configuration Status")
    print("=" * 40)

    for key in CONFIG_KEYS:
        value = config.get(key)
        source = sources.get(key, "not found")

        # Mask sensitive values
        display_value = value
        if key == "GEMINI_API_KEY" and value:
            display_value = "****" + value[-4:] if len(value) > 4 else "****"
        elif key == "DATABASE_URL" and value:
            display_value = s.masked_database_url()

        status_str = "✅ SET" if value else "❌ NOT SET"
        print(f"{key}: {status_str} (from {source})")
        if display_value and value:
            print(f"  Value: {display_value}")
        print()


if __name__ == "__main__":  # pragma: no cover
    print("Config:", get_config())
    print("DB URL:", get_database_url())
    print("Gemini:", get_gemini_config())
    print("Paths:", get_paths())
    print("Configured:", is_configured())
    print_config_debug()
