"""
Configuration Utilities for TESH-Query (v2 compatibility shim)

All functions delegate to teshq.config.settings.Settings (pydantic-settings).
The public API is preserved for backward compatibility with existing CLI code.

Functions:
- get_config()            → merged config as a plain dict
- save_config()           → persist config (secrets → .env, rest → yaml)
- get_database_url()      → DATABASE_URL value
- get_gemini_config()     → (api_key, model_name) tuple   [legacy: Gemini only]
- get_llm_config()        → dict with provider + all LLM settings
- get_paths()             → (output_path, file_store_path) tuple
- is_configured()         → True if DB + at least one LLM provider are set
- print_config_debug()    → human-readable debug summary
"""

import os
from typing import Any, Dict, Optional, Tuple

from teshq.config.secrets import SECRET_KEYS, save_secrets
from teshq.config.settings import save_secret, save_setting, get_settings

# Settings constants (kept for backward compat)
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash-lite"
SETTINGS_KEYS = {
    "GEMINI_MODEL",
    "OUTPUT_PATH",
    "FILE_STORE_PATH",
    "LLM_PROVIDER",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_DEPLOYMENT",
    "AZURE_OPENAI_API_VERSION",
    "LOCAL_MODEL_PATH",
    "LOCAL_N_GPU_LAYERS",
    "LOCAL_N_CTX",
    "LOCAL_N_THREADS",
}
CONFIG_KEYS = list(SECRET_KEYS) + list(SETTINGS_KEYS)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_config() -> Dict[str, Optional[str]]:
    """Return merged configuration as a plain dict (env vars win)."""
    try:
        s = get_settings(reload=True)
        return {
            "DATABASE_URL": s.database_url or None,
            "GEMINI_API_KEY": s.gemini_api_key or None,
            "GEMINI_MODEL": s.gemini_model,
            "OUTPUT_PATH": str(s.output_path),
            "FILE_STORE_PATH": str(s.file_store_path),
            "TESHQ_NO_TELEMETRY": str(s.no_telemetry).lower(),
            # Azure OpenAI
            "LLM_PROVIDER": s.llm_provider,
            "AZURE_OPENAI_API_KEY": s.azure_openai_api_key or None,
            "AZURE_OPENAI_ENDPOINT": s.azure_openai_endpoint or None,
            "AZURE_OPENAI_DEPLOYMENT": s.azure_openai_deployment or None,
            "AZURE_OPENAI_API_VERSION": s.azure_openai_api_version or None,
            # Local GGUF LLM
            "LOCAL_MODEL_PATH": s.local_model_path or None,
            "LOCAL_N_GPU_LAYERS": str(s.local_n_gpu_layers),
            "LOCAL_N_CTX": str(s.local_n_ctx),
            "LOCAL_N_THREADS": str(s.local_n_threads),
        }
    except Exception:
        # Graceful degradation if config files are completely broken/unreadable
        return {}


def get_config_with_source() -> Tuple[Dict[str, Optional[str]], Dict[str, str]]:
    """Return (config, sources) — sources maps key → origin string."""
    from teshq.config.paths import CONFIG_FILE, SECRETS_FILE
    from teshq.config.secrets import _read_env_file

    config = get_config()
    sources: Dict[str, str] = {}

    # Check secrets file
    env_data = _read_env_file(SECRETS_FILE)
    for key in SECRET_KEYS:
        if key in env_data and env_data[key]:
            sources[key] = "~/.teshq/.teshq.env"

    # Check YAML
    try:
        import yaml
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
                yaml_data = yaml.safe_load(fh) or {}
            for key in yaml_data:
                if key not in sources:
                    sources[key] = "~/.teshq/config.yaml"
    except Exception:
        pass

    # Env vars win
    for key in CONFIG_KEYS:
        if os.environ.get(key):
            sources[key] = "environment"

    config = {k: v for k, v in config.items() if v}
    sources = {k: v for k, v in sources.items() if k in config}
    return config, sources


def save_config(data: Dict[str, Optional[str]]) -> bool:
    """Save config entries — secrets to .env, others to config.yaml."""
    ok = True
    for key, value in data.items():
        if value is None:
            continue
        if key in SECRET_KEYS:
            ok = save_secret(key, value) and ok
        else:
            ok = save_setting(key, value) and ok
    return ok


def get_database_url() -> Optional[str]:
    """Return the configured DATABASE_URL, or None if not set."""
    return get_settings().database_url or None


def get_gemini_config() -> Tuple[Optional[str], str]:
    """Return (api_key, model_name) from current settings (Google Gemini)."""
    s = get_settings()
    return (s.gemini_api_key or None), s.gemini_model


def get_llm_config() -> Dict[str, Any]:
    """
    Return a provider-agnostic LLM configuration dict.

    Keys returned:
      - provider      → "google" | "azure" | "local"
      - api_key       → key for the chosen provider (may be None if not set)
      - model_name    → Gemini model name (Google) or deployment name (Azure)
      - azure_endpoint     → Azure OpenAI endpoint URL (Azure only)
      - azure_deployment   → Azure deployment name (Azure only)
      - azure_api_version  → Azure API version string (Azure only)
      - model_path    → Local model path (Local only)
      - n_gpu_layers  → GPU offload layers (Local only)
      - n_ctx         → Context window size (Local only)
      - n_threads     → Thread count (Local only)
    """
    s = get_settings()
    provider = s.effective_provider
    if provider == "local":
        return {
            "provider": "local",
            "model_path": s.local_model_path,
            "n_gpu_layers": s.local_n_gpu_layers,
            "n_ctx": s.local_n_ctx,
            "n_threads": s.local_n_threads,
        }
    if provider == "azure":
        return {
            "provider": "azure",
            "api_key": s.azure_openai_api_key or None,
            "model_name": s.azure_openai_deployment or None,
            "azure_endpoint": s.azure_openai_endpoint or None,
            "azure_deployment": s.azure_openai_deployment or None,
            "azure_api_version": s.azure_openai_api_version,
        }
    return {
        "provider": "google",
        "api_key": s.gemini_api_key or None,
        "model_name": s.gemini_model,
        "azure_endpoint": None,
        "azure_deployment": None,
        "azure_api_version": None,
    }


def get_storage_paths():
    """
    Get storage paths (backward compatibility shim).

    Returns a simple namespace with .schema, .metrics, .cache, .memory,
    .output, .files, and .logs paths — all under ~/.teshq/.
    """
    from teshq.config.paths import (
        SCHEMA_DIR, METRICS_DIR, CACHE_DIR, MEMORY_DIR,
        OUTPUT_DIR, FILES_DIR, LOGS_DIR, ensure_teshq_dir,
    )
    ensure_teshq_dir()

    class _Paths:
        schema = SCHEMA_DIR
        metrics = METRICS_DIR
        cache = CACHE_DIR
        memory = MEMORY_DIR
        output = OUTPUT_DIR
        files = FILES_DIR
        logs = LOGS_DIR
        # legacy alias
        query_results = OUTPUT_DIR

    return _Paths()


def get_paths() -> Tuple[str, str]:
    """Return (output_path, file_store_path) from current settings."""
    s = get_settings()
    return str(s.output_path), str(s.file_store_path)


def is_configured() -> bool:
    """Return True if DATABASE_URL and at least one LLM provider are set."""
    return get_settings().is_configured


def print_config_debug() -> None:
    """Print a human-readable debug summary of the current configuration."""
    config, sources = get_config_with_source()
    s = get_settings()

    print("🔍 Configuration Status")
    print("=" * 40)

    for key in CONFIG_KEYS:
        value = config.get(key)
        source = sources.get(key, "not found")

        # Mask sensitive values
        display_value = value
        if key in ("GEMINI_API_KEY", "AZURE_OPENAI_API_KEY") and value:
            display_value = "****" + value[-4:] if len(value) > 4 else "****"
        elif key == "DATABASE_URL" and value:
            display_value = s.masked_database_url()

        status_str = "✅ SET" if value else "❌ NOT SET"
        print(f"{key}: {status_str} (from {source})")
        if display_value and value:
            print(f"  Value: {display_value}")
        print()


if __name__ == "__main__":  # pragma: no cover
    print("Config:", get_config())
    print("DB URL:", get_database_url())
    print("Gemini:", get_gemini_config())
    print("LLM Config:", get_llm_config())
    print("Paths:", get_paths())
    print("Configured:", is_configured())
    print_config_debug()

