"""
Non-secret settings management for TESH-Query.

Non-sensitive configuration (model names, output paths, etc.) is stored in
~/.teshq/config.yaml using YAML format.  Secrets are handled separately in
teshq.config.secrets and are never written to this file.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from teshq.config.paths import CONFIG_FILE, ensure_teshq_dir

# Keys that belong in the YAML settings file (non-sensitive)
SETTINGS_KEYS = {"GEMINI_MODEL_NAME", "OUTPUT_PATH", "FILE_STORE_PATH"}

DEFAULT_SETTINGS: Dict[str, Any] = {
    "GEMINI_MODEL_NAME": "gemini-2.0-flash-lite",
    "OUTPUT_PATH": str(Path.home() / ".teshq" / "output"),
    "FILE_STORE_PATH": str(Path.home() / ".teshq" / "files"),
}


def _load_yaml(path: Path) -> Dict[str, Any]:
    """Load a YAML file and return its contents as a dict."""
    try:
        import yaml  # type: ignore
    except ImportError:
        return {}

    if not path.exists():
        return {}
    try:
        with open(path, "r") as fh:
            data = yaml.safe_load(fh) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_yaml(path: Path, data: Dict[str, Any]) -> None:
    """Write a dict to a YAML file."""
    try:
        import yaml  # type: ignore
    except ImportError:
        raise RuntimeError(
            "PyYAML is required for settings management. "
            "Install it with: pip install pyyaml"
        )

    ensure_teshq_dir()
    with open(path, "w") as fh:
        yaml.safe_dump(data, fh, default_flow_style=False, sort_keys=True)


def load_settings() -> Dict[str, Any]:
    """
    Load non-secret settings from ~/.teshq/config.yaml.

    Falls back to DEFAULT_SETTINGS for any missing keys.

    Returns:
        Dict of setting key → value.
    """
    on_disk = _load_yaml(CONFIG_FILE)
    merged = {**DEFAULT_SETTINGS, **on_disk}
    return merged


def save_settings(data: Dict[str, Optional[Any]]) -> bool:
    """
    Persist non-secret settings to ~/.teshq/config.yaml.

    Only keys listed in SETTINGS_KEYS are written.  Existing values for keys
    not present in *data* are preserved.

    Args:
        data: Mapping of setting key → value. Pass ``None`` to reset to default.

    Returns:
        bool: True on success, False on failure.
    """
    try:
        existing = _load_yaml(CONFIG_FILE)

        for key, value in data.items():
            if key not in SETTINGS_KEYS:
                continue
            if value is None:
                existing.pop(key, None)
            else:
                existing[key] = value

        _write_yaml(CONFIG_FILE, existing)
        return True
    except Exception as exc:
        print(f"Warning: could not save settings to {CONFIG_FILE}: {exc}")
        return False


def get_setting(key: str, default: Optional[Any] = None) -> Optional[Any]:
    """Return a single setting value, or *default* if not set."""
    return load_settings().get(key, default)
