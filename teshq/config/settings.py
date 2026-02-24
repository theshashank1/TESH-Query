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
    """
    Load YAML from a file and return its mapping contents.
    
    If PyYAML is not installed, the file does not exist, the parsed content is not a mapping, or any error occurs while reading/parsing, an empty dict is returned.
    
    Parameters:
        path (Path): Path to the YAML file to load.
    
    Returns:
        Dict[str, Any]: Parsed YAML mapping from the file, or an empty dict on error or when no mapping is present.
    """
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
    """
    Persist a mapping to the given filesystem path as a YAML document.
    
    Ensures the TESHQ configuration directory exists before writing the file.
    
    Parameters:
        path (Path): Filesystem path to write the YAML data to.
        data (Dict[str, Any]): Mapping to serialize into YAML.
    
    Raises:
        RuntimeError: If PyYAML is not installed.
        OSError: If opening or writing the file fails.
        Exception: If YAML serialization fails; underlying exception is propagated.
    """
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
    Load non-secret settings from the user's config file and merge them with defaults.
    
    On-disk values override DEFAULT_SETTINGS; keys missing on disk are filled from DEFAULT_SETTINGS.
    
    Returns:
        A dict mapping setting names to their resolved values.
    """
    on_disk = _load_yaml(CONFIG_FILE)
    merged = {**DEFAULT_SETTINGS, **on_disk}
    return merged


def save_settings(data: Dict[str, Optional[Any]]) -> bool:
    """
    Persist non-secret settings to the user's config file (~/.teshq/config.yaml).
    
    Only keys listed in SETTINGS_KEYS are written; keys not present in `data` are left unchanged. Passing `None` for a key removes it from the on-disk settings (resetting to the default).
    
    Parameters:
        data (Dict[str, Optional[Any]]): Mapping of setting keys to values. Use `None` to remove a key.
    
    Returns:
        `true` if the settings were written successfully, `false` otherwise.
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
    """
    Retrieve a non-secret setting by name.
    
    Parameters:
    	key (str): The setting key to look up.
    	default (Optional[Any]): Value to return if the setting is not present.
    
    Returns:
    	The stored value for `key`, or `default` if the key is not set.
    """
    return load_settings().get(key, default)
