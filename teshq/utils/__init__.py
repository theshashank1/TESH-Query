"""
TESH-Query Core Utilities Package
Configuration and core helper functions.

Author: theshashank1
Last Updated: 2025-06-19 17:11:04 UTC
"""

# Core configuration functions - used everywhere
from .config import (  # Essential constants
    CONFIG_KEYS,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_STORAGE_BASE_PATH,
    ENV_FILE,
    JSON_CONFIG_FILE,
    StoragePaths,
    get_config,
    get_current_timestamp,
    get_current_user,
    get_database_url,
    get_gemini_config,
    get_storage_paths,
    is_configured,
    save_config,
)

# Simple, focused public API - just the essentials
__all__ = [
    # Core functions
    "get_config",
    "save_config",
    "is_configured",
    "get_database_url",
    "get_gemini_config",
    "get_storage_paths",
    "get_current_timestamp",
    "get_current_user",
    # Essential constants
    "ENV_FILE",
    "JSON_CONFIG_FILE",
    "DEFAULT_GEMINI_MODEL",
    "DEFAULT_STORAGE_BASE_PATH",
    "CONFIG_KEYS",
    "StoragePaths",
]
