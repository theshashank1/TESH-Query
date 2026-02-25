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
SECRET_KEYS = {"DATABASE_URL", "GEMINI_API_KEY", "AZURE_OPENAI_API_KEY"}


def _read_env_file(path: Path) -> Dict[str, str]:
    """
    Parse a file of KEY=VALUE lines into a dictionary.
    
    Blank lines and lines starting with `#` are ignored. Lines without an `=` are skipped; keys and values have surrounding whitespace stripped. If the path does not exist or an I/O error occurs while reading, the function returns whatever was parsed up to that point (empty dict if nothing parsed).
    
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
                    result[key.strip()] = value.strip()
    except OSError:
        pass
    return result


def _write_env_file(path: Path, data: Dict[str, str]) -> None:
    """
    Write key/value pairs to a file in KEY=VALUE format and set the file to owner read/write only.
    
    Parameters:
        path (Path): Filesystem path to write the KEY=VALUE file to.
        data (Dict[str, str]): Mapping of keys to values to write; each pair is written as `KEY=VALUE` on its own line.
    
    Notes:
        Ensures the TESHQ configuration directory exists before writing and sets the file permission to 0o600 (owner read/write).
    """
    ensure_teshq_dir()
    content = "".join(f"{k}={v}\n" for k, v in data.items())
    path.write_text(content)
    # Restrict to owner read/write only
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def load_secrets() -> Dict[str, str]:
    """
    Load managed secrets from the local secrets file and apply environment-variable overrides.
    
    Environment variables with matching names take precedence over values read from the file.
    
    Returns:
        dict: Mapping of secret names to their values (environment variables override file values).
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
    Persist the allowed secret keys to the local secrets file (~/.teshq/.teshq.env).
    
    Only keys present in SECRET_KEYS are written; keys not included in `data` are left unchanged. Passing `None` for a key removes it from the file.
    
    Parameters:
        data (Dict[str, Optional[str]]): Mapping of secret key to value. Use `None` to remove a key.
    
    Returns:
        True if the file was written successfully, False otherwise.
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
    """
    Retrieve the stored secret value for the given key.
    
    Parameters:
        key (str): Name of the secret to fetch (e.g., one of the keys in SECRET_KEYS).
    
    Returns:
        The secret value for `key`, or `None` if it is not set.
    """
    return load_secrets().get(key)
