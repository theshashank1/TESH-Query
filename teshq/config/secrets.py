"""
Secrets management for TESH-Query.

Secrets (DATABASE_URL, GEMINI_API_KEY) are stored in ~/.teshq/.teshq.env
as a simple KEY=VALUE file, never in JSON and never in the project directory.

The file is created with 0o600 permissions (owner read/write only).
"""

import os
from pathlib import Path
from typing import Dict, Optional

from teshq.config.paths import SECRETS_FILE, ensure_teshq_dir

# Keys considered sensitive — stored only in the secrets file
SECRET_KEYS = {"DATABASE_URL", "GEMINI_API_KEY", "AZURE_OPENAI_API_KEY"}


def _read_env_file(path: Path) -> Dict[str, str]:
    """
    Parse a file of KEY=VALUE lines into a dictionary.

    Blank lines and comments are ignored. Keys and values are stripped of whitespace.

    Parameters:
        path (Path): Path to the KEY=VALUE file to read.

    Returns:
        Dict[str, str]: Mapping of keys to their corresponding values from the file.
    """
    result: Dict[str, str] = {}
    if not path.exists():
        return result
    try:
        with open(path, "r") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    result[key.strip()] = value.rstrip("\r\n")
    except OSError:
        pass
    return result


def _is_allowed_secret_key(key: str) -> bool:
    """Validate if key name is allowed to be saved as a secret."""
    import re
    if not isinstance(key, str) or not re.match(r"^[A-Z_][A-Z0-9_]*$", key):
        return False
    if key in SECRET_KEYS or key.startswith("TESHQ_"):
        return True
    return any(
        key.endswith(suffix)
        for suffix in ("_API_KEY", "_SECRET", "_TOKEN", "_PASSWORD", "_URL")
    )


def _write_env_file(path: Path, data: Dict[str, str]) -> None:
    """
    Write key/value pairs to a file in KEY=VALUE format atomically with 0o600 permissions.
    """
    ensure_teshq_dir()
    content = "".join(f"{k}={v}\n" for k, v in data.items())
    temp_path = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    fd = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, content.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temp_path, path)


def load_secrets() -> Dict[str, str]:
    """
    Load managed secrets from the local secrets file and apply environment-variable overrides.

    Environment variables with matching names take precedence over values read from the file.

    Returns:
        dict: Mapping of secret names to their values.
    """
    secrets = _read_env_file(SECRETS_FILE)

    # Environment variables override file values
    checked_keys = set(secrets.keys()).union(SECRET_KEYS)
    for key in checked_keys:
        env_val = os.environ.get(key)
        if env_val:
            secrets[key] = env_val

    # Also inherit any TESHQ_ environment variables
    for env_k, env_v in os.environ.items():
        if env_k.startswith("TESHQ_") and env_v:
            secrets[env_k] = env_v

    return secrets


def save_secrets(data: Dict[str, Optional[str]]) -> bool:
    """
    Persist the allowed secret keys to the local secrets file (~/.teshq/.teshq.env).

    Allows SECRET_KEYS, TESHQ_* prefixed keys (e.g. named DB passwords), and standard secret suffixes.
    Passing `None` for a key removes it from the file.

    Parameters:
        data (Dict[str, Optional[str]]): Mapping of secret key to value. Use `None` to remove a key.

    Returns:
        True if the file was written successfully, False otherwise.
    """
    try:
        existing = _read_env_file(SECRETS_FILE)

        for key, value in data.items():
            if not _is_allowed_secret_key(key):
                continue
            if value is None:
                existing.pop(key, None)
            else:
                existing[key] = str(value)

        _write_env_file(SECRETS_FILE, existing)
        return True
    except OSError as exc:
        # Avoid crashing the CLI; caller can surface the error
        print(f"Warning: could not save secrets to {SECRETS_FILE}: {exc}")
        return False


def get_secret(key: str) -> Optional[str]:
    """
    Retrieve the stored secret value for the given key.

    Parameters:
        key (str): Name of the secret to fetch (e.g., one of the keys in SECRET_KEYS).

    Returns:
        The secret value for `key`, or `None` if it is not set.
    """
    return load_secrets().get(key)
