"""
TESH-Query configuration package.

Provides a clean, single-directory configuration system rooted at ~/.teshq/.

Sub-modules:
  paths    – canonical paths for the config directory, secrets file, schema cache
  secrets  – secure storage for DATABASE_URL and GEMINI_API_KEY
  settings – YAML-based storage for non-secret configuration
"""

from teshq.config.paths import (
    CONFIG_FILE,
    LOGS_DIR,
    SCHEMA_DIR,
    SECRETS_FILE,
    TESHQ_DIR,
    ensure_teshq_dir,
    get_schema_path,
)
from teshq.config.secrets import (
    SECRET_KEYS,
    get_secret,
    load_secrets,
    save_secrets,
)
from teshq.config.settings import (
    DEFAULT_SETTINGS,
    SETTINGS_KEYS,
    get_setting,
    load_settings,
    save_settings,
)

__all__ = [
    # paths
    "TESHQ_DIR",
    "SECRETS_FILE",
    "CONFIG_FILE",
    "SCHEMA_DIR",
    "LOGS_DIR",
    "ensure_teshq_dir",
    "get_schema_path",
    # secrets
    "SECRET_KEYS",
    "load_secrets",
    "save_secrets",
    "get_secret",
    # settings
    "SETTINGS_KEYS",
    "DEFAULT_SETTINGS",
    "load_settings",
    "save_settings",
    "get_setting",
]
