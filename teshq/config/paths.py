"""
Path definitions for TESH-Query configuration directory.

All configuration, secrets, and schema cache are stored under ~/.teshq/
to provide a clean, single-directory configuration system.
"""

from pathlib import Path

# Base configuration directory: ~/.teshq/
TESHQ_DIR = Path.home() / ".teshq"

# Secrets file (stores DATABASE_URL, GEMINI_API_KEY — never in plain JSON)
SECRETS_FILE = TESHQ_DIR / ".teshq.env"

# YAML configuration file for non-secret settings
CONFIG_FILE = TESHQ_DIR / "config.yaml"

# Database schema cache directory
SCHEMA_DIR = TESHQ_DIR / "schema"

# Logs directory
LOGS_DIR = TESHQ_DIR / "logs"


def ensure_teshq_dir() -> Path:
    """
    Ensure the ~/.teshq/ directory and its sub-directories exist.

    Returns:
        Path: The ~/.teshq/ directory path.
    """
    TESHQ_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return TESHQ_DIR


def get_schema_path(filename: str = "schema.txt") -> Path:
    """Return the path to a schema file inside ~/.teshq/schema/."""
    return SCHEMA_DIR / filename
