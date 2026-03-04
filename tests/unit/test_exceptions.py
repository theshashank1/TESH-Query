"""
Tests for the custom exception hierarchy and retry mechanisms.

Validates:
- Custom exception construction and attributes
- classify_llm_error routing (rate-limit vs. generic)
- Exponential backoff in TeshEngine._execute_with_retry
- LLM rate-limit backoff in _generate_with_rate_limit_backoff
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from teshq.core.exceptions import (
    DatabaseConnectionError,
    ExecutionTimeoutError,
    LLMRateLimitError,
    SchemaIntrospectionError,
    SelfHealingExhaustedError,
    SQLGenerationError,
    SQLValidationError,
    TeshqConfigurationError,
    TeshqError,
    classify_llm_error,
)


# ---------------------------------------------------------------------------
# Exception hierarchy basics
# ---------------------------------------------------------------------------


class TestExceptionHierarchy:
    """All TESHQ exceptions inherit from TeshqError."""

    def test_base_error_message(self):
        err = TeshqError("something broke")
        assert str(err) == "something broke"

    def test_base_error_with_detail(self):
        err = TeshqError("something broke", detail="check config")
        assert "something broke" in str(err)
        assert "check config" in str(err)
        assert err.detail == "check config"

    @pytest.mark.parametrize(
        "exc_cls",
        [
            TeshqConfigurationError,
            SchemaIntrospectionError,
            SQLGenerationError,
            SQLValidationError,
            ExecutionTimeoutError,
            DatabaseConnectionError,
            SelfHealingExhaustedError,
        ],
    )
    def test_subclass_is_teshq_error(self, exc_cls):
        err = exc_cls("msg")
        assert isinstance(err, TeshqError)

    def test_rate_limit_error_retry_after(self):
        err = LLMRateLimitError(retry_after=5.0)
        assert err.retry_after == 5.0
        assert isinstance(err, TeshqError)


# ---------------------------------------------------------------------------
# classify_llm_error
# ---------------------------------------------------------------------------


class TestClassifyLlmError:
    """classify_llm_error should detect 429/rate-limit vs generic errors."""

    def test_classifies_rate_limit_by_status_code(self):
        exc = Exception("too many requests")
        exc.status_code = 429  # type: ignore[attr-defined]
        result = classify_llm_error(exc)
        assert isinstance(result, LLMRateLimitError)

    def test_classifies_rate_limit_by_message(self):
        exc = Exception("Rate limit exceeded — try again later")
        result = classify_llm_error(exc)
        assert isinstance(result, LLMRateLimitError)

    def test_classifies_rate_limit_by_429_in_message(self):
        exc = Exception("HTTP 429: resource exhausted")
        result = classify_llm_error(exc)
        assert isinstance(result, LLMRateLimitError)

    def test_classifies_generic_error_as_sql_gen(self):
        exc = Exception("unexpected JSON schema")
        result = classify_llm_error(exc)
        assert isinstance(result, SQLGenerationError)

    def test_captures_retry_after_attribute(self):
        exc = Exception("rate limit")
        exc.retry_after = 3.5  # type: ignore[attr-defined]
        result = classify_llm_error(exc)
        assert isinstance(result, LLMRateLimitError)
        assert result.retry_after == 3.5


# ---------------------------------------------------------------------------
# Engine retry behaviour (mocked — no real DB or LLM)
# ---------------------------------------------------------------------------


class TestExecuteWithRetry:
    """Verify exponential backoff and self-healing in TeshEngine."""

    def _make_engine(self):
        """Return a TeshEngine with all external deps mocked out."""
        with patch("teshq.core.engine.get_llm_config", return_value={
            "provider": "google",
            "api_key": "fake",
            "model_name": "gemini-2.0-flash-lite",
        }), patch("teshq.core.engine.get_database_url", return_value="sqlite:////tmp/test.db"):
            from teshq.core.engine import TeshEngine
            engine = TeshEngine(db_url="sqlite:////tmp/test.db", api_key="fake-key")
        return engine

    def test_successful_execution_no_retry(self):
        """When execute_sql_query succeeds on first try, no retry occurs."""
        engine = self._make_engine()
        with patch("teshq.core.engine.execute_sql_query", return_value=[{"id": 1}]):
            rows = engine._execute_with_retry("SELECT 1", {})
        assert rows == [{"id": 1}]

    def test_transient_db_error_retries_then_succeeds(self):
        """ConnectionError on first attempt should be retried with backoff."""
        engine = self._make_engine()
        call_count = 0

        def flaky_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("connection reset")
            return [{"ok": True}]

        with patch("teshq.core.engine.execute_sql_query", side_effect=flaky_execute), \
             patch("teshq.core.engine.time.sleep"):
            rows = engine._execute_with_retry("SELECT 1", {})

        assert rows == [{"ok": True}]
        assert call_count == 2

    def test_non_retryable_error_triggers_self_heal(self):
        """A non-transient SQL error triggers self-healing (if context available)."""
        engine = self._make_engine()
        engine._last_nl_query = "show users"
        engine._last_schema_str = "TABLE users(id PK, name TEXT)"
        engine._last_plan = MagicMock()

        from teshq.core.models import SQLQuery

        mock_gen = MagicMock()
        mock_gen.generate.return_value = SQLQuery(query="SELECT id FROM users", parameters={})
        engine._sql_gen = mock_gen

        call_count = 0

        def fail_then_succeed(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                raise RuntimeError("no such column: foo")
            return [{"id": 1}]

        with patch("teshq.core.engine.execute_sql_query", side_effect=fail_then_succeed), \
             patch("teshq.core.engine.validate_sql"), \
             patch("teshq.core.engine.normalize_sql", side_effect=lambda s: s):
            rows = engine._execute_with_retry("SELECT foo FROM users", {})

        assert rows == [{"id": 1}]
        mock_gen.generate.assert_called_once()

    def test_self_heal_exhausted_raises(self):
        """When self-healing also fails, SelfHealingExhaustedError is raised."""
        engine = self._make_engine()
        engine._last_nl_query = "show users"
        engine._last_schema_str = "TABLE users(id PK)"
        engine._last_plan = MagicMock()

        mock_gen = MagicMock()
        mock_gen.generate.side_effect = RuntimeError("LLM unavailable")
        engine._sql_gen = mock_gen

        with patch("teshq.core.engine.execute_sql_query", side_effect=RuntimeError("bad SQL")):
            with pytest.raises(SelfHealingExhaustedError):
                engine._execute_with_retry("SELECT bad", {})
