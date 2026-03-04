"""Unit tests for teshq.config.settings (no disk I/O — uses env vars only)."""

import os
import pytest
from pathlib import Path

@pytest.fixture(autouse=True)
def clear_env_vars(monkeypatch):
    """Clear all configuration env vars by setting them empty so tests run in a clean vacuum.
    This supersedes any local .env file loads by pydantic."""
    for key in [
        "DATABASE_URL", "GEMINI_API_KEY",
        "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT", "AZURE_OPENAI_API_VERSION"
    ]:
        monkeypatch.setenv(key, "")
    
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("TESHQ_NO_TELEMETRY", raising=False)
    
    # Prevent loading from actual ~/.teshq/.env on dev machine
    monkeypatch.setattr("teshq.config.paths.SECRETS_FILE", Path("/nonexistent/.env"))
    # Prevent YAML config source from loading actual config.yaml
    monkeypatch.setattr("teshq.config.settings.CONFIG_FILE", Path("/nonexistent/config.yaml"))

class TestSettingsDefaults:
    def test_defaults_without_env(self):
        """Settings should load without raising even if secrets are missing."""

        from importlib import reload
        import teshq.config.settings as mod
        mod._settings_cache = None  # clear cache

        s = mod.get_settings()
        assert s.database_url == ""
        assert s.gemini_api_key == ""
        assert s.gemini_model == "gemini-2.0-flash-lite"
        assert s.no_telemetry is False

    def test_is_configured_false(self):
        from importlib import reload
        import teshq.config.settings as mod
        mod._settings_cache = None

        s = mod.get_settings()
        assert s.is_configured is False

    def test_is_configured_true(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
        monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
        
        import teshq.config.settings as mod
        mod._settings_cache = None

        s = mod.get_settings()
        assert s.is_configured is True

    def test_no_telemetry_env(self, monkeypatch):
        monkeypatch.setenv("TESHQ_NO_TELEMETRY", "1")
        
        import teshq.config.settings as mod
        mod._settings_cache = None

        s = mod.get_settings()
        assert s.no_telemetry is True

    def test_masked_database_url_empty(self):
        import teshq.config.settings as mod
        mod._settings_cache = None

        s = mod.get_settings()
        assert s.masked_database_url() == "(not set)"

    def test_masked_database_url_masks_password(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:secretpassword@localhost/mydb")
        
        import teshq.config.settings as mod
        mod._settings_cache = None

        s = mod.get_settings()
        masked = s.masked_database_url()
        assert "secretpassword" not in masked
        # SQLAlchemy masks with *** (3 stars)
        assert "***" in masked
