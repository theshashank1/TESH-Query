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
    Ensure the TESHQ base directory and its schema/log subdirectories exist.
    
    Creates the base directory with mode 0o700 (owner read/write/execute) and creates the schema and logs directories if missing.
    
    Returns:
        Path: The base TESHQ directory path.
    """
    TESHQ_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return TESHQ_DIR


def get_schema_path(filename: str = "schema.txt") -> Path:
    """
    Get the filesystem path for a schema file located in the schema cache directory.
    
    @returns Path to the specified schema file inside the schema directory.
    """
    return SCHEMA_DIR / filename
