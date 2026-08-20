"""
Unit tests for the LLM Factory (core/llm_factory.py).

All tests are fully offline — no real API calls are made.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from teshq.core.llm_factory import build_llm, build_llm_from_config, _build_google_llm, _build_azure_llm


class TestBuildLlmProviderRouting:
    """Test that build_llm() routes to the correct provider."""

    def test_google_provider_builds_google_llm(self):
        mock_llm = MagicMock()
        with patch("teshq.core.llm_factory._build_google_llm", return_value=mock_llm) as mock_builder:
            result = build_llm(
                provider="google",
                api_key="AIzatest123",
                model_name="gemini-2.0-flash-lite",
            )
            mock_builder.assert_called_once()
            assert result is mock_llm

    def test_azure_provider_builds_azure_llm(self):
        mock_llm = MagicMock()
        with patch("teshq.core.llm_factory._build_azure_llm", return_value=mock_llm) as mock_builder:
            result = build_llm(
                provider="azure",
                api_key="sk-test",
                azure_endpoint="https://myresource.openai.azure.com/",
                azure_deployment="gpt-4o",
            )
            mock_builder.assert_called_once()
            assert result is mock_llm

    def test_unsupported_provider_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            build_llm(provider="anthropic")

    def test_provider_is_case_insensitive(self):
        mock_llm = MagicMock()
        with patch("teshq.core.llm_factory._build_google_llm", return_value=mock_llm):
            # Should not raise
            build_llm(provider="GOOGLE", api_key="AIzatest123")

    def test_azure_provider_case_insensitive(self):
        mock_llm = MagicMock()
        with patch("teshq.core.llm_factory._build_azure_llm", return_value=mock_llm):
            build_llm(
                provider="Azure",
                api_key="sk-test",
                azure_endpoint="https://res.openai.azure.com/",
                azure_deployment="gpt-4",
            )


class TestBuildGoogleLlm:
    """Unit tests for _build_google_llm()."""

    def test_raises_if_no_api_key(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(ValueError, match="Gemini API key is not set"):
            _build_google_llm(api_key=None, model_name="gemini-2.0-flash-lite", temperature=0, top_p=1, top_k=1)

    def test_uses_api_key_from_argument(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        mock_llm = MagicMock()
        with patch("langchain_google_genai.ChatGoogleGenerativeAI", return_value=mock_llm) as mock_cls:
            result = _build_google_llm(
                api_key="AIzaFakeKey",
                model_name="gemini-2.0-flash-lite",
                temperature=0,
                top_p=1,
                top_k=1,
            )
            mock_cls.assert_called_once()
            assert result is mock_llm

    def test_uses_env_var_google_api_key(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "AIzaFromEnv")
        mock_llm = MagicMock()
        with patch("langchain_google_genai.ChatGoogleGenerativeAI", return_value=mock_llm):
            result = _build_google_llm(api_key=None, model_name=None, temperature=0, top_p=1, top_k=1)
            assert result is mock_llm

    def test_uses_env_var_gemini_api_key(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.setenv("GEMINI_API_KEY", "AIzaGeminiEnv")
        mock_llm = MagicMock()
        with patch("langchain_google_genai.ChatGoogleGenerativeAI", return_value=mock_llm):
            result = _build_google_llm(api_key=None, model_name=None, temperature=0, top_p=1, top_k=1)
            assert result is mock_llm

    def test_default_model_used_when_none(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "AIzaTest")
        with patch("langchain_google_genai.ChatGoogleGenerativeAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            _build_google_llm(api_key=None, model_name=None, temperature=0, top_p=1, top_k=1)
            call_kwargs = mock_cls.call_args[1]
            assert call_kwargs["model"] == "gemini-2.0-flash-lite"

    def test_missing_langchain_google_genai_raises_import_error(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "AIzaTest")
        import sys
        orig = sys.modules.get("langchain_google_genai")
        try:
            sys.modules["langchain_google_genai"] = None
            with pytest.raises((ImportError, TypeError)):
                _build_google_llm(api_key="key", model_name="model", temperature=0, top_p=1, top_k=1)
        finally:
            if orig is None:
                sys.modules.pop("langchain_google_genai", None)
            else:
                sys.modules["langchain_google_genai"] = orig


class TestBuildAzureLlm:
    """Unit tests for _build_azure_llm()."""

    def test_raises_if_no_api_key(self, monkeypatch):
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
        with pytest.raises(ValueError, match="Azure OpenAI API key is not set"):
            _build_azure_llm(api_key=None, deployment="dep", endpoint="https://ep.openai.azure.com/", api_version=None, temperature=0)

    def test_raises_if_no_endpoint(self, monkeypatch):
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        with pytest.raises(ValueError, match="Azure OpenAI endpoint is not set"):
            _build_azure_llm(api_key="sk-test", deployment="dep", endpoint=None, api_version=None, temperature=0)

    def test_raises_if_no_deployment(self, monkeypatch):
        monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)
        with pytest.raises(ValueError, match="Azure OpenAI deployment name is not set"):
            _build_azure_llm(
                api_key="sk-test",
                deployment=None,
                endpoint="https://ep.openai.azure.com/",
                api_version=None,
                temperature=0,
            )

    def test_builds_azure_llm_with_explicit_args(self):
        mock_llm = MagicMock()
        with patch("langchain_openai.AzureChatOpenAI", return_value=mock_llm) as mock_cls:
            result = _build_azure_llm(
                api_key="sk-test",
                deployment="gpt-4o",
                endpoint="https://myresource.openai.azure.com/",
                api_version="2024-02-01",
                temperature=0,
            )
            mock_cls.assert_called_once_with(
                azure_endpoint="https://myresource.openai.azure.com/",
                azure_deployment="gpt-4o",
                api_key="sk-test",
                api_version="2024-02-01",
                temperature=0,
            )
            assert result is mock_llm

    def test_uses_env_vars(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "sk-env")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://env.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4-env")
        mock_llm = MagicMock()
        with patch("langchain_openai.AzureChatOpenAI", return_value=mock_llm):
            result = _build_azure_llm(api_key=None, deployment=None, endpoint=None, api_version=None, temperature=0)
            assert result is mock_llm

    def test_default_api_version_used(self, monkeypatch):
        monkeypatch.delenv("AZURE_OPENAI_API_VERSION", raising=False)
        mock_llm = MagicMock()
        with patch("langchain_openai.AzureChatOpenAI", return_value=mock_llm) as mock_cls:
            _build_azure_llm(
                api_key="sk-test",
                deployment="gpt-4o",
                endpoint="https://res.openai.azure.com/",
                api_version=None,
                temperature=0,
            )
            call_kwargs = mock_cls.call_args[1]
            assert call_kwargs["api_version"] == "2024-10-21"


class TestBuildLlmFromConfig:
    """Test build_llm_from_config() reads app settings correctly."""

    def test_delegates_to_build_llm_with_google(self):
        mock_llm = MagicMock()
        google_config = {
            "provider": "google",
            "api_key": "AIzaFake",
            "model_name": "gemini-2.0-flash-lite",
            "azure_endpoint": None,
            "azure_deployment": None,
            "azure_api_version": None,
        }
        with patch("teshq.config.loader.get_llm_config", return_value=google_config):
            with patch("teshq.core.llm_factory.build_llm", return_value=mock_llm) as mock_build:
                result = build_llm_from_config()
                mock_build.assert_called_once_with(
                    provider="google",
                    api_key="AIzaFake",
                    model_name="gemini-2.0-flash-lite",
                    azure_endpoint=None,
                    azure_deployment=None,
                    azure_api_version=None,
                )
                assert result is mock_llm

    def test_delegates_to_build_llm_with_azure(self):
        mock_llm = MagicMock()
        azure_config = {
            "provider": "azure",
            "api_key": "sk-azure",
            "model_name": "gpt-4o",
            "azure_endpoint": "https://res.openai.azure.com/",
            "azure_deployment": "gpt-4o",
            "azure_api_version": "2024-02-01",
        }
        with patch("teshq.config.loader.get_llm_config", return_value=azure_config):
            with patch("teshq.core.llm_factory.build_llm", return_value=mock_llm) as mock_build:
                result = build_llm_from_config()
                mock_build.assert_called_once_with(
                    provider="azure",
                    api_key="sk-azure",
                    model_name="gpt-4o",
                    azure_endpoint="https://res.openai.azure.com/",
                    azure_deployment="gpt-4o",
                    azure_api_version="2024-02-01",
                )
                assert result is mock_llm
