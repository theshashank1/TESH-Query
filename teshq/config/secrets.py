"""
Secrets management for TESH-Query.

Secrets (DATABASE_URL, GEMINI_API_KEY) are stored in ~/.teshq/.teshq.env
as a simple KEY=VALUE file, never in JSON and never in the project directory.

The file is created with 0o600 permissions (owner read/write only).
"""

import os
import stat
from pathlib import Path
from typing import Dict, Optional

from teshq.config.paths import SECRETS_FILE, ensure_teshq_dir

# Keys considered sensitive — stored only in the secrets file
SECRET_KEYS = {"DATABASE_URL", "GEMINI_API_KEY"}


def _read_env_file(path: Path) -> Dict[str, str]:
    """Parse a KEY=VALUE file and return a dict (skips blank lines and comments)."""
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
                    result[key.strip()] = value.strip()
    except OSError:
        pass
    return result


def _write_env_file(path: Path, data: Dict[str, str]) -> None:
    """Write a KEY=VALUE file with restricted permissions (0o600)."""
    ensure_teshq_dir()
    content = "".join(f"{k}={v}\n" for k, v in data.items())
    path.write_text(content)
    # Restrict to owner read/write only
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def load_secrets() -> Dict[str, str]:
    """
    Load secrets from ~/.teshq/.teshq.env, then overlay environment variables.

    Environment variables always take precedence over the secrets file.

    Returns:
        Dict mapping secret key names to their values.
    """
    secrets = _read_env_file(SECRETS_FILE)

    # Environment variables override file values
    for key in SECRET_KEYS:
        env_val = os.environ.get(key)
        if env_val:
            secrets[key] = env_val

    return secrets


def save_secrets(data: Dict[str, Optional[str]]) -> bool:
    """
    Persist secrets to ~/.teshq/.teshq.env.

    Only keys listed in SECRET_KEYS are written.  Existing values for keys
    not present in *data* are preserved.

    Args:
        data: Mapping of secret key → value. Pass ``None`` to remove a key.

    Returns:
        bool: True on success, False on failure.
    """
    try:
        existing = _read_env_file(SECRETS_FILE)

        for key, value in data.items():
            if key not in SECRET_KEYS:
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
    """Return a single secret value, or None if not set."""
    return load_secrets().get(key)
