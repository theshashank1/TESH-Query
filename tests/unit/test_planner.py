"""
Tests for QueryPlanner — covers both Google (structured output) and
Azure (plain text + JSON parse) paths, including the empty SQL guard
in TeshEngine and the SchemaRetriever wiring.
"""

from unittest.mock import MagicMock, patch

import pytest

from teshq.core.models import QueryPlan
from teshq.core.planner import QueryPlanner
from teshq.core.retriever import SchemaRetriever
from teshq.core.schema_graph import JoinEdge, SchemaGraph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_graph() -> SchemaGraph:
    return SchemaGraph(
        tables={
            "users": ["id PK", "name TEXT", "email TEXT"],
            "orders": ["id PK", "user_id FK→users.id", "total DECIMAL"],
        },
        joins=[JoinEdge(left_table="orders", right_table="users", left_column="user_id", right_column="id")],
        summary="",
    )


# ---------------------------------------------------------------------------
# QueryPlanner — Google path (structured output)
# ---------------------------------------------------------------------------


class TestQueryPlannerGoogle:
    """Test the Google (structured output) planner path."""

    def _make_planner(self, plan_return):
        mock_llm = MagicMock()
        structured_llm = MagicMock()
        structured_llm.invoke.return_value = plan_return
        mock_llm.with_structured_output.return_value = structured_llm
        return QueryPlanner(mock_llm, provider="google")

    def test_plan_returns_query_plan(self):
        expected_plan = QueryPlan(
            tables=["users"],
            filters=["name = alice"],
            aggregations=[],
            joins_needed=[],
        )
        planner = self._make_planner(expected_plan)
        result = planner.plan("find user alice", "TABLE users(id PK, name TEXT)")
        assert result.tables == ["users"]
        assert result.filters == ["name = alice"]

    def test_uses_structured_output_for_google(self):
        mock_llm = MagicMock()
        structured_llm = MagicMock()
        structured_llm.invoke.return_value = QueryPlan(
            tables=["t"], filters=[], aggregations=[], joins_needed=[]
        )
        mock_llm.with_structured_output.return_value = structured_llm
        planner = QueryPlanner(mock_llm, provider="google")

        assert planner._structured_llm is structured_llm
        mock_llm.with_structured_output.assert_called_once_with(QueryPlan)

    def test_retries_on_parse_error(self):
        """Planner should retry up to 2 extra times on ValidationError."""
        mock_llm = MagicMock()
        structured_llm = MagicMock()
        call_count = 0

        def side_effect(messages):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Simulated parse failure")
            return QueryPlan(tables=["users"], filters=[], aggregations=[], joins_needed=[])

        structured_llm.invoke.side_effect = side_effect
        mock_llm.with_structured_output.return_value = structured_llm
        planner = QueryPlanner(mock_llm, provider="google")

        result = planner.plan("test query", "TABLE users(id PK)")
        assert result.tables == ["users"]
        assert call_count == 3


# ---------------------------------------------------------------------------
# QueryPlanner — Azure path (plain text + JSON parse)
# ---------------------------------------------------------------------------


class TestQueryPlannerAzure:
    """Test the Azure plain-text fallback planner path."""

    def _make_azure_planner(self, response_content: str):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = response_content
        mock_llm.invoke.return_value = mock_response
        return QueryPlanner(mock_llm, provider="azure")

    def test_azure_skips_structured_output(self):
        mock_llm = MagicMock()
        planner = QueryPlanner(mock_llm, provider="azure")
        assert planner._structured_llm is None
        mock_llm.with_structured_output.assert_not_called()

    def test_azure_parses_plain_json_response(self):
        json_resp = '{"tables": ["orders"], "filters": ["status = active"], "aggregations": [], "joins_needed": []}'
        planner = self._make_azure_planner(json_resp)
        result = planner.plan("active orders", "TABLE orders(id PK, status TEXT)")
        assert result.tables == ["orders"]
        assert result.filters == ["status = active"]

    def test_azure_strips_markdown_fences(self):
        json_resp = '```json\n{"tables": ["users"], "filters": [], "aggregations": [], "joins_needed": []}\n```'
        planner = self._make_azure_planner(json_resp)
        result = planner.plan("all users", "TABLE users(id PK)")
        assert result.tables == ["users"]

    def test_azure_retries_on_json_parse_error(self):
        """Azure path should retry when JSON is malformed."""
        mock_llm = MagicMock()
        call_count = 0
        good_response = MagicMock()
        good_response.content = '{"tables": ["users"], "filters": [], "aggregations": [], "joins_needed": []}'
        bad_response = MagicMock()
        bad_response.content = "This is not JSON at all"

        def side_effect(messages):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return bad_response
            return good_response

        mock_llm.invoke.side_effect = side_effect
        planner = QueryPlanner(mock_llm, provider="azure")
        result = planner.plan("find users", "TABLE users(id PK)")
        assert result.tables == ["users"]
        assert call_count == 2


# ---------------------------------------------------------------------------
# Engine — empty SQL guard
# ---------------------------------------------------------------------------


class TestEnginEmptySqlGuard:
    """Verify that TeshEngine raises SQLGenerationError on empty LLM output."""

    def _make_engine(self):
        with patch("teshq.core.engine.get_llm_config", return_value={
            "provider": "google",
            "api_key": "fake-key",
            "model_name": "gemini-2.0-flash-lite",
        }), patch("teshq.core.engine.get_database_url", return_value="sqlite:///test.db"):
            from teshq.core.engine import TeshEngine
            return TeshEngine(db_url="sqlite:///test.db", api_key="fake-key")

    def test_empty_sql_raises_generation_error(self):
        from teshq.core.exceptions import SQLGenerationError
        from teshq.core.models import QueryPlan, SQLQuery

        engine = self._make_engine()
        dummy_plan = QueryPlan(tables=["users"], filters=[], aggregations=[], joins_needed=[])
        dummy_graph = _sample_graph()

        with patch.object(engine, "_get_planner") as mock_planner_factory, \
             patch.object(engine, "_get_sql_gen") as mock_sql_gen_factory:

            mock_planner = MagicMock()
            mock_planner.plan.return_value = dummy_plan
            mock_planner_factory.return_value = mock_planner

            mock_gen = MagicMock()
            # LLM returns empty SQL
            mock_gen.generate.return_value = SQLQuery(query="", parameters={})
            mock_sql_gen_factory.return_value = mock_gen

            with pytest.raises(SQLGenerationError, match="empty query"):
                engine.query("find users", schema_graph=dummy_graph)


# ---------------------------------------------------------------------------
# Engine — SchemaRetriever is used (not prune_schema)
# ---------------------------------------------------------------------------


class TestEngineUsesSchemaRetriever:
    """Verify that TeshEngine now uses SchemaRetriever, not prune_schema."""

    def test_retriever_is_used_not_pruner(self):
        """
        Check that SchemaRetriever.retrieve is called during engine.query().
        If prune_schema() were still used, SchemaRetriever.retrieve would never be called.
        """
        with patch("teshq.core.engine.get_llm_config", return_value={
            "provider": "google",
            "api_key": "fake",
            "model_name": "gemini-2.0-flash-lite",
        }), patch("teshq.core.engine.get_database_url", return_value="sqlite:///test.db"):
            from teshq.core.engine import TeshEngine
            engine = TeshEngine(db_url="sqlite:///test.db", api_key="fake")

        dummy_graph = _sample_graph()
        from teshq.core.models import QueryPlan, SQLQuery

        with patch("teshq.core.engine.SchemaRetriever") as MockRetriever, \
             patch.object(engine, "_get_planner") as mock_planner_factory, \
             patch.object(engine, "_get_sql_gen") as mock_sql_gen_factory:

            # Setup mock retriever
            mock_retriever_instance = MagicMock()
            mock_retriever_instance.retrieve.return_value = ["users", "orders"]
            MockRetriever.return_value = mock_retriever_instance

            mock_planner = MagicMock()
            mock_planner.plan.return_value = QueryPlan(
                tables=["users"], filters=[], aggregations=[], joins_needed=[]
            )
            mock_planner_factory.return_value = mock_planner

            mock_gen = MagicMock()
            mock_gen.generate.return_value = SQLQuery(
                query="SELECT id, name FROM users", parameters={}
            )
            mock_sql_gen_factory.return_value = mock_gen

            with patch("teshq.core.engine.execute_sql_query", return_value=[{"id": 1}]):
                engine.query("show all users", schema_graph=dummy_graph)

            # Retriever must have been called
            MockRetriever.assert_called_once_with(dummy_graph)
            mock_retriever_instance.retrieve.assert_called_once()
