"""
Tests for the SDK (TeshQuery) and async interfaces.

Validates:
- TeshQuery initialisation and validation
- TeshQuery.aquery() async execution
- TeshEngine.aquery() async execution
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# TeshQuery initialisation
# ---------------------------------------------------------------------------


class TestTeshQueryInit:
    """Verify SDK validation logic during __init__."""

    def test_raises_without_db_url(self):
        with patch("teshq.api.get_config", return_value={}):
            with pytest.raises(ValueError, match="Database URL is required"):
                from teshq.api import TeshQuery

                TeshQuery()

    def test_raises_without_gemini_key(self):
        with patch("teshq.api.get_config", return_value={"DATABASE_URL": "sqlite:///x.db"}):
            with pytest.raises(ValueError, match="Gemini API key is required"):
                from teshq.api import TeshQuery

                TeshQuery(db_url="sqlite:///x.db")

    def test_creates_google_client(self):
        with patch("teshq.api.get_config", return_value={}):
            from teshq.api import TeshQuery

            client = TeshQuery(db_url="sqlite:///x.db", gemini_api_key="test-key")
            assert client._provider == "google"
            assert client.gemini_api_key == "test-key"

    def test_creates_azure_client(self):
        with patch("teshq.api.get_config", return_value={}):
            from teshq.api import TeshQuery

            client = TeshQuery(
                db_url="sqlite:///x.db",
                provider="azure",
                azure_api_key="az-key",
                azure_endpoint="https://myresource.openai.azure.com/",
                azure_deployment="gpt-4o",
            )
            assert client._provider == "azure"
            assert client.azure_api_key == "az-key"


# ---------------------------------------------------------------------------
# TeshQuery.aquery (async)
# ---------------------------------------------------------------------------


class TestTeshQueryAsync:
    """Test async query method on TeshQuery."""

    @pytest.mark.asyncio
    async def test_aquery_delegates_to_sync_query(self):
        """aquery() should call query() in a thread executor and return results."""
        with patch("teshq.api.get_config", return_value={}):
            from teshq.api import TeshQuery

            client = TeshQuery(db_url="sqlite:///x.db", gemini_api_key="test-key")

        mock_result = [{"id": 1, "name": "Alice"}]
        with patch.object(client, "query", return_value=mock_result) as mock_query:
            result = await client.aquery("show all users")

        mock_query.assert_called_once_with("show all users", return_sql=False)
        assert result == mock_result

    @pytest.mark.asyncio
    async def test_aquery_with_return_sql(self):
        """aquery(return_sql=True) should pass through to query()."""
        with patch("teshq.api.get_config", return_value={}):
            from teshq.api import TeshQuery

            client = TeshQuery(db_url="sqlite:///x.db", gemini_api_key="test-key")

        mock_result = {"sql": "SELECT 1", "parameters": {}, "results": []}
        with patch.object(client, "query", return_value=mock_result):
            result = await client.aquery("test", return_sql=True)

        assert result == mock_result


# ---------------------------------------------------------------------------
# TeshEngine.aquery (async)
# ---------------------------------------------------------------------------


class TestTeshEngineAsync:
    """Test async query method on TeshEngine."""

    def _make_engine(self):
        with patch("teshq.core.engine.get_llm_config", return_value={
            "provider": "google",
            "api_key": "fake",
            "model_name": "gemini-2.0-flash-lite",
        }), patch("teshq.core.engine.get_database_url", return_value="sqlite:////tmp/test.db"):
            from teshq.core.engine import TeshEngine

            return TeshEngine(db_url="sqlite:////tmp/test.db", api_key="fake-key")

    @pytest.mark.asyncio
    async def test_aquery_delegates_to_sync(self):
        engine = self._make_engine()

        from teshq.core.engine import QueryResult

        mock_result = QueryResult(
            nl_query="test",
            plan=None,
            sql="SELECT 1",
            parameters={},
            rows=[{"v": 1}],
            dry_run=False,
            plan_latency_ms=0,
            sql_latency_ms=0,
            exec_latency_ms=0,
        )
        with patch.object(engine, "query", return_value=mock_result):
            result = await engine.aquery("test query")

        assert result.sql == "SELECT 1"
        assert result.rows == [{"v": 1}]
