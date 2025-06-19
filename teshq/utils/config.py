"""
Simple Configuration Utilities for TESH-Query

Provides functions for retrieving, saving, and validating configuration
from environment variables, .env file, and config.json file.

Functions:
- get_config(): Retrieve merged configuration.
- save_config(): Save configuration data to .env and config.json files.
- get_database_url(): Get the database connection URL.
- get_gemini_config(): Get Gemini API key and model name.
- get_paths(): Get output and file storage paths.
- is_configured(): Check if essential configuration is present.
- print_config_debug(): Print detailed configuration status for debugging.
"""

import json
import os
from datetime import datetime
from typing import Dict, Optional, Tuple

# Constants
ENV_FILE = ".env"
JSON_CONFIG_FILE = "config.json"
DEFAULT_GEMINI_MODEL = "gemini-1.5-flash-latest"
DEFAULT_OUTPUT_PATH = "./teshq_output"
DEFAULT_FILE_STORE_PATH = "./teshq_files"

CONFIG_KEYS = ["DATABASE_URL", "GEMINI_API_KEY", "GEMINI_MODEL_NAME", "OUTPUT_PATH", "FILE_STORE_PATH"]


def get_current_timestamp() -> str:
    """Get current UTC timestamp."""
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def get_current_user() -> str:
    """Get current user login."""
    return os.getenv("USER") or os.getenv("USERNAME") or "theshashank1"


def get_config() -> Dict[str, Optional[str]]:
    """
    Get configuration with fallback priority:
    1. Environment variables
    2. .env file
    3. config.json file
    """
    config = {}

    # Start with JSON file (lowest priority)
    if os.path.exists(JSON_CONFIG_FILE):
        try:
            with open(JSON_CONFIG_FILE, "r") as f:
                data = json.load(f)
                for key in CONFIG_KEYS:
                    if key in data and data[key]:
                        config[key] = data[key]
        except (IOError, json.JSONDecodeError):
            pass

    # Override with .env file (medium priority)
    if os.path.exists(ENV_FILE):
        try:
            with open(ENV_FILE, "r") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        key = key.strip()
                        if key in CONFIG_KEYS and value.strip():
                            config[key] = value.strip()
        except IOError as e:
            print(f"Error reading .env file: {e}")

    # Override with environment variables (highest priority)
    for key in CONFIG_KEYS:
        env_value = os.getenv(key)
        if env_value:
            config[key] = env_value

    return config


def get_config_with_source() -> Tuple[Dict[str, Optional[str]], Dict[str, str]]:
    """Get configuration with source information."""
    config = {}
    sources = {}

    for key in CONFIG_KEYS:
        value = None
        source = "not_found"

        # Check environment variable first
        env_value = os.getenv(key)
        if env_value:
            value = env_value
            source = "environment"
        else:
            # Check .env file
            if os.path.exists(ENV_FILE):
                try:
                    with open(ENV_FILE, "r") as f:
                        for line in f:
                            line = line.strip()
                            if "=" in line and not line.startswith("#"):
                                k, v = line.split("=", 1)
                                if k.strip() == key and v.strip():
                                    value = v.strip()
                                    source = "env_file"
                                    break
                except IOError as e:
                    print(f"Error reading .env file in get_config_with_source: {e}")

            # Check JSON file if not found in .env
            if not value and os.path.exists(JSON_CONFIG_FILE):
                try:
                    with open(JSON_CONFIG_FILE, "r") as f:
                        data = json.load(f)
                        if key in data and data[key]:
                            value = data[key]
                            source = "json_file"
                except (IOError, json.JSONDecodeError) as e:
                    print(f"Error reading config.json in get_config_with_source: {e}")
                    pass

        if value:
            config[key] = value
            sources[key] = source

    return config, sources


def save_config(data: Dict[str, Optional[str]]) -> bool:
    """Save configuration to both .env and JSON files."""
    try:
        # Update .env file
        env_vars = {}
        if os.path.exists(ENV_FILE):
            with open(ENV_FILE, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        env_vars[key.strip()] = value.strip()

        # Update with new data
        for key, value in data.items():
            if value is not None:
                env_vars[key] = str(value)
            elif key in env_vars:
                del env_vars[key]

        # Write .env file
        with open(ENV_FILE, "w") as f:
            for key, value in env_vars.items():
                f.write(f"{key}={value}\n")

        # Update JSON file (same data + metadata)
        json_config = {}
        if os.path.exists(JSON_CONFIG_FILE):
            try:
                with open(JSON_CONFIG_FILE, "r") as f:
                    json_config = json.load(f)
            except (IOError, json.JSONDecodeError):
                pass

        # Update with new data
        for key, value in data.items():
            if value is not None:
                json_config[key] = value
            elif key in json_config:
                del json_config[key]

        # Add metadata
        json_config["last_updated"] = get_current_timestamp()
        json_config["updated_by"] = get_current_user()

        # Write JSON file
        with open(JSON_CONFIG_FILE, "w") as f:
            json.dump(json_config, f, indent=4)

        return True
    except IOError as e:
        print(f"IOError saving config: {e}")
        return False


def get_database_url() -> Optional[str]:
    """Get database URL."""
    config = get_config()
    return config.get("DATABASE_URL")


def get_gemini_config() -> Tuple[Optional[str], str]:
    """Get Gemini API key and model."""
    config = get_config()
    api_key = config.get("GEMINI_API_KEY")
    model = config.get("GEMINI_MODEL_NAME", DEFAULT_GEMINI_MODEL)
    return api_key, model


def get_paths() -> Tuple[str, str]:
    """Get output and file store paths."""
    config = get_config()
    output_path = config.get("OUTPUT_PATH", DEFAULT_OUTPUT_PATH)
    file_store_path = config.get("FILE_STORE_PATH", DEFAULT_FILE_STORE_PATH)
    return output_path, file_store_path


def is_configured() -> bool:
    """Check if required configuration is present."""
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

        status = "✅ SET" if value else "❌ NOT SET"
        print(f"{key}: {status} (from {source})")
        if display_value and value:
            print(f"  Value: {display_value}")
        print()


if __name__ == "__main__":
    print("Get all config:", get_config())
    print("Get config with source:", get_config_with_source())
    # print("Save config:", save_config({"DATABASE_URL": "postgresql://user:pass@host:port/dbname"}))
    print("Get DB URL:", get_database_url())
    print("Get Gemini config:", get_gemini_config())
    print("Get paths:", get_paths())
    print("Is configured:", is_configured())
    print_config_debug()
