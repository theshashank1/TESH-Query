"""
TESH-Query v2 Settings — single source of truth for all configuration.

Priority (highest → lowest):
  1. Environment variables (DATABASE_URL, GEMINI_API_KEY, AZURE_OPENAI_API_KEY, …)
  2. ~/.teshq/.env  (secrets file, never committed)
  3. ~/.teshq/config.yaml  (non-secret settings)
  4. Hard-coded defaults below
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from teshq.config.paths import CONFIG_FILE, SECRETS_FILE, ensure_teshq_dir

# ---------------------------------------------------------------------------
# Keys that are secrets (go to .env) vs general settings (go to config.yaml)
# ---------------------------------------------------------------------------
SECRET_KEYS = {
    "DATABASE_URL",
    "GEMINI_API_KEY",
    "AZURE_OPENAI_API_KEY",
}
SETTINGS_KEYS = {
    "GEMINI_MODEL",
    "OUTPUT_PATH",
    "FILE_STORE_PATH",
    "NO_TELEMETRY",
    "LLM_PROVIDER",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_DEPLOYMENT",
    "AZURE_OPENAI_API_VERSION",
}


class Settings(BaseSettings):
    """
    All TESH-Query runtime configuration in one typed model.

    Usage::

        from teshq.config.settings import get_settings
        s = get_settings()
        print(s.gemini_model)
        print(s.llm_provider)  # "google" or "azure"
    """

    # --- Secrets (loaded from env or ~/.teshq/.env) ---
    database_url: str = Field(default="", alias="DATABASE_URL")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")

    # --- Azure OpenAI secrets ---
    azure_openai_api_key: str = Field(default="", alias="AZURE_OPENAI_API_KEY")

    # --- LLM provider selection ---
    llm_provider: str = Field(default="google", alias="LLM_PROVIDER")

    # --- Non-secret settings (Google Gemini) ---
    gemini_model: str = Field(default="gemini-2.0-flash-lite", alias="GEMINI_MODEL")

    # --- Non-secret settings (Azure OpenAI) ---
    azure_openai_endpoint: str = Field(default="", alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_deployment: str = Field(default="", alias="AZURE_OPENAI_DEPLOYMENT")
    azure_openai_api_version: str = Field(default="2024-02-01", alias="AZURE_OPENAI_API_VERSION")

    # --- Storage paths ---
    output_path: Path = Field(
        default_factory=lambda: Path.home() / ".teshq" / "output",
        alias="OUTPUT_PATH",
    )
    file_store_path: Path = Field(
        default_factory=lambda: Path.home() / ".teshq" / "files",
        alias="FILE_STORE_PATH",
    )
    no_telemetry: bool = Field(default=False, alias="TESHQ_NO_TELEMETRY")

    model_config = SettingsConfigDict(
        env_file=str(SECRETS_FILE),
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )

    @field_validator("output_path", "file_store_path", mode="before")
    @classmethod
    def coerce_path(cls, v: Any) -> Path:
        return Path(v) if not isinstance(v, Path) else v

    @property
    def is_configured(self) -> bool:
        """Return True if the database and at least one LLM provider are configured."""
        db_ok = bool(self.database_url)
        google_ok = bool(self.gemini_api_key)
        azure_ok = bool(self.azure_openai_api_key) and bool(self.azure_openai_endpoint) and bool(self.azure_openai_deployment)
        return db_ok and (google_ok or azure_ok)

    @property
    def effective_provider(self) -> str:
        """
        Return the effective LLM provider string.

        If ``LLM_PROVIDER`` is explicitly set to ``"azure"`` (or Azure keys are
        present and no Gemini key is set), return ``"azure"``; otherwise
        ``"google"``.
        """
        if self.llm_provider.lower() == "azure":
            return "azure"
        # Auto-detect: if Azure is fully configured but Gemini key is absent
        azure_ready = bool(self.azure_openai_api_key) and bool(self.azure_openai_endpoint)
        if azure_ready and not self.gemini_api_key:
            return "azure"
        return "google"

    def masked_database_url(self) -> str:
        """Return the database URL with the password replaced by ****."""
        if not self.database_url:
            return "(not set)"
        try:
            from sqlalchemy.engine import make_url
            url = make_url(self.database_url)
            return str(url._replace(password="****")) if url.password else self.database_url
        except Exception:
            return self.database_url


# ---------------------------------------------------------------------------
# Singleton helper — cached per-process
# ---------------------------------------------------------------------------
_settings_cache: Optional[Settings] = None


def get_settings(reload: bool = False) -> Settings:
    """Return the cached Settings instance, creating it on first call."""
    global _settings_cache
    if _settings_cache is None or reload:
        _settings_cache = Settings()
    return _settings_cache


# ---------------------------------------------------------------------------
# Save helpers (write back to disk)
# ---------------------------------------------------------------------------

def save_secret(key: str, value: str) -> bool:
    """
    Persist a single secret key=value to ~/.teshq/.env.

    Reads the existing file, updates the key, and rewrites — so other
    secrets are not lost.
    """
    ensure_teshq_dir()
    env_vars: Dict[str, str] = {}

    if SECRETS_FILE.exists():
        for line in SECRETS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                env_vars[k.strip()] = v.strip()

    env_vars[key] = value

    try:
        SECRETS_FILE.write_text(
            "\n".join(f"{k}={v}" for k, v in env_vars.items()) + "\n",
            encoding="utf-8",
        )
        SECRETS_FILE.chmod(0o600)  # owner-read-only
        os.environ[key] = value    # update current process too
        global _settings_cache
        _settings_cache = None     # invalidate cache
        return True
    except OSError as exc:
        print(f"Warning: could not save secret to {SECRETS_FILE}: {exc}")
        return False


def save_setting(key: str, value: Any) -> bool:
    """
    Persist a single non-secret setting to ~/.teshq/config.yaml.
    """
    ensure_teshq_dir()
    try:
        import yaml
    except ImportError:
        print("Warning: pyyaml is required to save settings.")
        return False

    existing: Dict[str, Any] = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
                existing = yaml.safe_load(fh) or {}
        except Exception:
            pass

    existing[key] = str(value) if isinstance(value, Path) else value

    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
            yaml.safe_dump(existing, fh, default_flow_style=False, sort_keys=True)
        global _settings_cache
        _settings_cache = None  # invalidate cache
        return True
    except OSError as exc:
        print(f"Warning: could not save setting to {CONFIG_FILE}: {exc}")
        return False

