"""
Unit tests for Azure OpenAI configuration in Settings and get_llm_config().
"""

import os
from unittest.mock import patch
from pathlib import Path

import pytest

from teshq.config.settings import Settings

@pytest.fixture(autouse=True)
def clear_env_vars(monkeypatch):
    """Clear all configuration env vars so tests run in a clean vacuum.
    Prevents leakage from actual ~/.teshq/.env and ~/.teshq/config.yaml."""
    for key in [
        "DATABASE_URL", "GEMINI_API_KEY",
        "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT"
    ]:
        monkeypatch.setenv(key, "")
    
    monkeypatch.delenv("AZURE_OPENAI_API_VERSION", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("TESHQ_NO_TELEMETRY", raising=False)
    
    # Prevent loading from actual ~/.teshq/.env on dev machine
    monkeypatch.setitem(Settings.model_config, "env_file", None)

    # Prevent the new YAML config source from loading actual config.yaml
    monkeypatch.setattr("teshq.config.settings.CONFIG_FILE", Path("/nonexistent/config.yaml"))


class TestSettingsAzureFields:
    """Verify that Settings correctly loads Azure OpenAI fields."""

    def test_default_provider_is_google(self):
        s = Settings()
        assert s.llm_provider == "google"

    def test_effective_provider_google_when_gemini_key_set(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "AIzaFake")
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
        s = Settings()
        assert s.effective_provider == "google"

    def test_effective_provider_azure_when_provider_set(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "azure")
        s = Settings()
        assert s.effective_provider == "azure"

    def test_effective_provider_auto_detects_azure(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "sk-fake")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://res.openai.azure.com/")
        monkeypatch.setenv("LLM_PROVIDER", "google")  # explicit google but no gemini key
        s = Settings()
        # auto-detect: azure keys present, gemini absent → azure
        assert s.effective_provider == "azure"

    def test_is_configured_with_google(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
        monkeypatch.setenv("GEMINI_API_KEY", "AIzaFake")
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
        s = Settings()
        assert s.is_configured is True

    def test_is_configured_with_azure(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "sk-fake")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://res.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
        s = Settings()
        assert s.is_configured is True

    def test_is_configured_false_without_db(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("GEMINI_API_KEY", "AIzaFake")
        s = Settings()
        assert s.is_configured is False

    def test_is_configured_false_without_any_llm(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
        s = Settings()
        assert s.is_configured is False

    def test_azure_default_api_version(self):
        s = Settings()
        assert s.azure_openai_api_version == "2024-02-01"


class TestGetLlmConfig:
    """Verify that get_llm_config() returns correct dicts for each provider."""

    def test_returns_google_config(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "AIzaFake")
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("LLM_PROVIDER", "google")

        from teshq.config.settings import _settings_cache
        import teshq.config.settings as settings_module
        settings_module._settings_cache = None  # force reload

        from teshq.config.loader import get_llm_config
        cfg = get_llm_config()
        assert cfg["provider"] == "google"
        assert cfg["api_key"] == "AIzaFake"
        assert "azure_endpoint" in cfg

    def test_returns_azure_config(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "azure")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "sk-azure")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://res.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        import teshq.config.settings as settings_module
        settings_module._settings_cache = None

        from teshq.config.loader import get_llm_config
        cfg = get_llm_config()
        assert cfg["provider"] == "azure"
        assert cfg["api_key"] == "sk-azure"
        assert cfg["azure_endpoint"] == "https://res.openai.azure.com/"
        assert cfg["azure_deployment"] == "gpt-4o"
