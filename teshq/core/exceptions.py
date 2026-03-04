"""
Custom exception hierarchy for TESH-Query v2.

Provides categorized, user-friendly exceptions that never leak raw
stack traces to CLI or API consumers. All failures are typed and
include actionable context for debugging.
"""

from typing import Optional


class TeshqError(Exception):
    """Base exception for all TESH-Query errors."""

    def __init__(self, message: str, detail: Optional[str] = None) -> None:
        self.detail = detail
        full = f"{message} — {detail}" if detail else message
        super().__init__(full)


class TeshqConfigurationError(TeshqError):
    """Raised when required configuration is missing or invalid.

    Examples: missing API key, invalid DATABASE_URL, unsupported provider.
    """


class SchemaIntrospectionError(TeshqError):
    """Raised when database schema introspection fails.

    Examples: connection refused, permission denied on information_schema,
    unsupported dialect.
    """


class SQLGenerationError(TeshqError):
    """Raised when the LLM fails to produce valid SQL.

    Examples: malformed structured output, empty query, non-SELECT when
    read-only mode is expected.
    """


class SQLValidationError(TeshqError):
    """Raised when generated SQL fails safety or syntax validation."""


class ExecutionTimeoutError(TeshqError):
    """Raised when a SQL query exceeds the configured timeout."""


class DatabaseConnectionError(TeshqError):
    """Raised for transient or permanent database connectivity failures."""


class LLMRateLimitError(TeshqError):
    """Raised when the LLM provider returns a rate-limit (HTTP 429) error.

    Includes the ``retry_after`` hint when the upstream API provides one.
    """

    def __init__(
        self,
        message: str = "LLM rate limit exceeded",
        detail: Optional[str] = None,
        retry_after: Optional[float] = None,
    ) -> None:
        self.retry_after = retry_after
        super().__init__(message, detail)


class SelfHealingExhaustedError(TeshqError):
    """Raised when the self-healing retry loop has exhausted all attempts."""


def classify_llm_error(exc: Exception) -> Exception:
    """Inspect a raw LLM exception and return a typed TESHQ exception.

    Recognises HTTP-429 (rate limit) errors from common provider SDKs
    and wraps them in :class:`LLMRateLimitError`.  All other errors are
    wrapped as :class:`SQLGenerationError`.
    """
    msg = str(exc).lower()
    status: Optional[int] = getattr(exc, "status_code", None) or getattr(
        exc, "code", None
    )

    if status == 429 or "429" in msg or "rate limit" in msg or "too many requests" in msg:
        retry_after: Optional[float] = None
        ra = getattr(exc, "retry_after", None)
        if ra is not None:
            try:
                retry_after = float(ra)
            except (TypeError, ValueError):
                pass
        return LLMRateLimitError(
            message="LLM rate limit exceeded",
            detail=str(exc),
            retry_after=retry_after,
        )

    return SQLGenerationError(
        message="SQL generation failed",
        detail=str(exc),
    )
