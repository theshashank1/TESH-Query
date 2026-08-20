"""
Path definitions for TESH-Query configuration directory.

All configuration, secrets, schema cache, logs, memory, and output
are stored under ~/.teshq/ to provide a clean, single-directory
configuration system.

Directory layout:
  ~/.teshq/
  ├── .teshq.env          # Secrets (DATABASE_URL, API keys)
  ├── config.yaml         # Non-secret settings
  ├── schema/             # Database schema cache (JSON + text)
  │   ├── schema.json
  │   ├── schema.txt      # Compact DDL (used by LLM)
  │   └── schema_full.txt # Verbose schema (optional)
  ├── cache/              # General purpose key-value cache
  ├── memory/             # Conversation / session memory
  ├── metrics/            # Usage analytics JSONL
  ├── output/             # Default query result exports
  ├── files/              # User uploaded/exported files
  └── logs/               # Log files
"""

from pathlib import Path
import hashlib


# Base configuration directory: ~/.teshq/
TESHQ_DIR = Path.home() / ".teshq"

# Secrets file (stores DATABASE_URL, GEMINI_API_KEY — never in plain JSON)
SECRETS_FILE = TESHQ_DIR / ".teshq.env"

# YAML configuration file for non-secret settings
CONFIG_FILE = TESHQ_DIR / "config.yaml"

# Database schema cache directory
SCHEMA_DIR = TESHQ_DIR / "schema"

# General purpose cache directory
CACHE_DIR = TESHQ_DIR / "cache"

# Conversation / session memory directory
MEMORY_DIR = TESHQ_DIR / "memory"

# Usage metrics directory
METRICS_DIR = TESHQ_DIR / "metrics"

# Default query result output directory
OUTPUT_DIR = TESHQ_DIR / "output"

# User file store directory
FILES_DIR = TESHQ_DIR / "files"

# Logs directory
LOGS_DIR = TESHQ_DIR / "logs"


def ensure_teshq_dir() -> Path:
    """
    Ensure the TESHQ base directory and all subdirectories exist.

    Creates the base directory with mode 0o700 (owner read/write/execute)
    and creates all required subdirectories if missing.

    Returns:
        Path: The base TESHQ directory path.
    """
    TESHQ_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    for subdir in (SCHEMA_DIR, CACHE_DIR, MEMORY_DIR, METRICS_DIR, OUTPUT_DIR, FILES_DIR, LOGS_DIR):
        subdir.mkdir(parents=True, exist_ok=True)
    return TESHQ_DIR


def get_schema_path(filename: str = "schema.txt") -> Path:
    """
    Get the filesystem path for a schema file in the schema cache directory.

    Args:
        filename: Schema file name (e.g. 'schema.json', 'schema.txt').

    Returns:
        Path to the specified schema file inside the schema directory.
    """
    return SCHEMA_DIR / filename


def get_db_schema_path(db_url: str, filename: str = "schema.txt") -> Path:
    """
    Get a per-database schema cache path using a stable hash of the DB URL.

    This allows multiple databases to coexist in the schema cache without
    collision. The sub-directory name is a short hex hash of the URL.

    Args:
        db_url: Database connection URL (used to compute the cache key).
        filename: Schema file name (default: 'schema.txt').

    Returns:
        Path to the schema file inside a per-DB subdirectory.
    """
    db_hash = hashlib.sha1(db_url.encode()).hexdigest()[:12]
    db_schema_dir = SCHEMA_DIR / db_hash
    db_schema_dir.mkdir(parents=True, exist_ok=True)
    return db_schema_dir / filename


def get_cache_path(key: str) -> Path:
    """
    Get a path inside the general cache directory.

    Args:
        key: Cache entry filename (e.g. 'embeddings.pkl').

    Returns:
        Path to the cache file.
    """
    return CACHE_DIR / key


def get_memory_path(session_id: str = "default") -> Path:
    """
    Get a path for storing conversation/session memory.

    Args:
        session_id: Session identifier (default: 'default').

    Returns:
        Path to the memory file for the given session.
    """
    return MEMORY_DIR / f"{session_id}.json"
