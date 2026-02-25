"""
TESH-Query configuration package.

Provides a clean, single-directory configuration system rooted at ~/.teshq/.

Sub-modules:
  paths    – canonical paths for the config directory, secrets file, schema cache
  secrets  – secure storage for DATABASE_URL and GEMINI_API_KEY
  settings – pydantic-settings based Settings model (v2)
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
from teshq.config.settings import (
    Settings,
    get_settings,
    save_secret,
    save_setting,
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
    # settings (v2)
    "Settings",
    "get_settings",
    "save_secret",
    "save_setting",
]
