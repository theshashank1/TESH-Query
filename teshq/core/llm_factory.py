"""
LLM Factory for TESH-Query v2.

Provides a single entry-point, ``build_llm()``, that returns a LangChain
chat-model configured for the chosen provider (Google Gemini or Azure OpenAI).

Supported providers
-------------------
* ``"google"``  — ChatGoogleGenerativeAI (requires GEMINI_API_KEY)
* ``"azure"``   — AzureChatOpenAI (requires AZURE_OPENAI_API_KEY,
                                     AZURE_OPENAI_ENDPOINT,
                                     AZURE_OPENAI_DEPLOYMENT)

Environment variables used (if not supplied explicitly):
  GOOGLE_API_KEY            → Gemini API key (alias for GEMINI_API_KEY)
  GEMINI_API_KEY            → Gemini API key
  AZURE_OPENAI_API_KEY      → Azure OpenAI API key
  AZURE_OPENAI_ENDPOINT     → Azure OpenAI resource endpoint URL
  AZURE_OPENAI_DEPLOYMENT   → Azure OpenAI deployment/model name
  AZURE_OPENAI_API_VERSION  → Azure OpenAI API version (default: 2024-02-01)
  LLM_PROVIDER              → "google" or "azure" (overrides auto-detection)
"""

from __future__ import annotations

import os
from typing import Any, Optional

_AZURE_DEFAULT_API_VERSION = "2024-02-01"


def build_llm(
    provider: str = "google",
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    # Azure-specific
    azure_endpoint: Optional[str] = None,
    azure_deployment: Optional[str] = None,
    azure_api_version: Optional[str] = None,
    # Common LLM settings
    temperature: float = 0,
    top_p: float = 1,
    top_k: int = 1,
) -> Any:
    """
    Create and return a LangChain chat model for the given *provider*.

    Parameters
    ----------
    provider:
        ``"google"`` (Gemini) or ``"azure"`` (Azure OpenAI).
    api_key:
        API key for the provider.  Falls back to the corresponding environment
        variable if not supplied.
    model_name:
        Model/deployment to use.  Defaults differ per provider.
    azure_endpoint:
        Azure OpenAI resource endpoint URL (Azure only).
    azure_deployment:
        Azure deployment name (Azure only; usually same as *model_name*).
    azure_api_version:
        Azure API version string (Azure only).
    temperature, top_p, top_k:
        Sampling parameters.  Keep at defaults (0 / 1 / 1) for deterministic
        output.

    Returns
    -------
    A LangChain ``BaseChatModel`` instance.

    Raises
    ------
    ValueError
        If required credentials are missing for the chosen provider.
    ImportError
        If the required LangChain integration package is not installed.
    """
    provider = (provider or "google").lower().strip()

    if provider == "azure":
        return _build_azure_llm(
            api_key=api_key,
            deployment=azure_deployment or model_name,
            endpoint=azure_endpoint,
            api_version=azure_api_version,
            temperature=temperature,
        )
    elif provider == "google":
        return _build_google_llm(
            api_key=api_key,
            model_name=model_name,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
        )
    else:
        raise ValueError(
            f"Unsupported LLM provider: {provider!r}. "
            "Choose 'google' (Gemini) or 'azure' (Azure OpenAI)."
        )


# ---------------------------------------------------------------------------
# Private builders
# ---------------------------------------------------------------------------

def _build_google_llm(
    api_key: Optional[str],
    model_name: Optional[str],
    temperature: float,
    top_p: float,
    top_k: int,
) -> Any:
    """Build a ChatGoogleGenerativeAI instance."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as exc:
        raise ImportError(
            "langchain-google-genai is required for the Google Gemini provider. "
            "Install it with: pip install langchain-google-genai"
        ) from exc

    # Resolve API key
    resolved_key = (
        api_key
        or os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
    )
    if not resolved_key:
        raise ValueError(
            "Gemini API key is not set. "
            "Set the GEMINI_API_KEY environment variable or pass api_key=."
        )

    # Ensure the env var is set for the SDK
    if not os.environ.get("GOOGLE_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = resolved_key

    resolved_model = model_name or "gemini-2.0-flash-lite"

    return ChatGoogleGenerativeAI(
        model=resolved_model,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
    )


def _build_azure_llm(
    api_key: Optional[str],
    deployment: Optional[str],
    endpoint: Optional[str],
    api_version: Optional[str],
    temperature: float,
) -> Any:
    """Build an AzureChatOpenAI instance."""
    try:
        from langchain_openai import AzureChatOpenAI
    except ImportError as exc:
        raise ImportError(
            "langchain-openai is required for the Azure OpenAI provider. "
            "Install it with: pip install langchain-openai"
        ) from exc

    # Resolve credentials from args → env vars
    resolved_key = api_key or os.environ.get("AZURE_OPENAI_API_KEY")
    resolved_endpoint = endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT")
    resolved_deployment = deployment or os.environ.get("AZURE_OPENAI_DEPLOYMENT")
    resolved_version = (
        api_version
        or os.environ.get("AZURE_OPENAI_API_VERSION")
        or _AZURE_DEFAULT_API_VERSION
    )

    if not resolved_key:
        raise ValueError(
            "Azure OpenAI API key is not set. "
            "Set the AZURE_OPENAI_API_KEY environment variable or pass api_key=."
        )
    if not resolved_endpoint:
        raise ValueError(
            "Azure OpenAI endpoint is not set. "
            "Set the AZURE_OPENAI_ENDPOINT environment variable or pass azure_endpoint=."
        )
    if not resolved_deployment:
        raise ValueError(
            "Azure OpenAI deployment name is not set. "
            "Set the AZURE_OPENAI_DEPLOYMENT environment variable or pass azure_deployment=."
        )

    return AzureChatOpenAI(
        azure_endpoint=resolved_endpoint,
        azure_deployment=resolved_deployment,
        api_key=resolved_key,
        api_version=resolved_version,
        temperature=temperature,
    )


def build_llm_from_config() -> Any:
    """
    Build an LLM from the current application configuration.

    Reads ``get_llm_config()`` and delegates to ``build_llm()``.
    This is the preferred entry-point for application code that doesn't
    want to pass credentials explicitly.

    Returns
    -------
    A configured LangChain BaseChatModel instance.
    """
    from teshq.config.loader import get_llm_config

    cfg = get_llm_config()
    return build_llm(
        provider=cfg["provider"],
        api_key=cfg["api_key"],
        model_name=cfg["model_name"],
        azure_endpoint=cfg.get("azure_endpoint"),
        azure_deployment=cfg.get("azure_deployment"),
        azure_api_version=cfg.get("azure_api_version"),
    )
