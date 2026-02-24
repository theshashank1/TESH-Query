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
    get_config,
    get_config_with_source,
    get_database_url,
    get_gemini_config,
    get_paths,
    is_configured,
    save_config,
)

# Simple, focused public API - just the essentials
__all__ = [
    # Core functions
    "get_config",
    "get_config_with_source",
    "save_config",
    "is_configured",
    "get_database_url",
    "get_gemini_config",
    "get_paths",
    # Essential constants
    "DEFAULT_GEMINI_MODEL",
    "CONFIG_KEYS",
]
