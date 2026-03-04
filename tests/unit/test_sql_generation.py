"""
Tests for the SQL generation pipeline.

Mocks the LLM to validate:
- SchemaRetriever Top-K table selection
- SQLGenerator structured output parsing
- Integration between retriever and generator
"""

from unittest.mock import MagicMock, patch

import pytest

from teshq.core.models import QueryPlan, SQLQuery
from teshq.core.retriever import SchemaRetriever
from teshq.core.schema_graph import JoinEdge, SchemaGraph


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _sample_schema_graph() -> SchemaGraph:
    """Build a small but realistic schema graph for testing."""
    return SchemaGraph(
        tables={
            "users": ["id PK", "name TEXT", "email TEXT", "created_at TIMESTAMP"],
            "orders": ["id PK", "user_id FK→users.id", "total DECIMAL", "status TEXT"],
            "products": ["id PK", "name TEXT", "price DECIMAL", "category TEXT"],
            "order_items": ["id PK", "order_id FK→orders.id", "product_id FK→products.id", "quantity INT"],
            "categories": ["id PK", "name TEXT"],
            "reviews": ["id PK", "user_id FK→users.id", "product_id FK→products.id", "rating INT"],
            "payments": ["id PK", "order_id FK→orders.id", "amount DECIMAL", "method TEXT"],
            "addresses": ["id PK", "user_id FK→users.id", "city TEXT", "country TEXT"],
        },
        joins=[
            JoinEdge(left_table="orders", right_table="users", left_column="user_id", right_column="id"),
            JoinEdge(left_table="order_items", right_table="orders", left_column="order_id", right_column="id"),
            JoinEdge(left_table="order_items", right_table="products", left_column="product_id", right_column="id"),
            JoinEdge(left_table="reviews", right_table="users", left_column="user_id", right_column="id"),
            JoinEdge(left_table="reviews", right_table="products", left_column="product_id", right_column="id"),
            JoinEdge(left_table="payments", right_table="orders", left_column="order_id", right_column="id"),
            JoinEdge(left_table="addresses", right_table="users", left_column="user_id", right_column="id"),
        ],
        summary="",
    )


# ---------------------------------------------------------------------------
# SchemaRetriever tests
# ---------------------------------------------------------------------------


class TestSchemaRetriever:
    """Test TF-IDF-based schema retrieval."""

    def test_retrieves_relevant_tables_for_orders_query(self):
        graph = _sample_schema_graph()
        retriever = SchemaRetriever(graph)
        tables = retriever.retrieve("show me all orders", top_k=3)
        assert "orders" in tables

    def test_retrieves_users_and_neighbors(self):
        graph = _sample_schema_graph()
        retriever = SchemaRetriever(graph)
        tables = retriever.retrieve("list users", top_k=2, expand_neighbors=True)
        assert "users" in tables
        # FK neighbors of users should be included
        assert any(t in tables for t in ["orders", "reviews", "addresses"])

    def test_retrieves_products_for_price_query(self):
        graph = _sample_schema_graph()
        retriever = SchemaRetriever(graph)
        tables = retriever.retrieve("product price", top_k=3)
        assert "products" in tables

    def test_no_match_falls_back_to_most_connected(self):
        graph = _sample_schema_graph()
        retriever = SchemaRetriever(graph)
        tables = retriever.retrieve("zzz xyz obscure", top_k=3)
        # Should return something (most connected fallback)
        assert len(tables) > 0

    def test_expand_neighbors_false(self):
        graph = _sample_schema_graph()
        retriever = SchemaRetriever(graph)
        tables = retriever.retrieve("payments", top_k=1, expand_neighbors=False)
        assert "payments" in tables
        # Without expansion, we might not get neighbors
        assert len(tables) <= 2  # at most the directly matched tables

    def test_empty_query_falls_back(self):
        graph = _sample_schema_graph()
        retriever = SchemaRetriever(graph)
        tables = retriever.retrieve("", top_k=3)
        assert len(tables) > 0

    def test_retriever_reviews_query(self):
        graph = _sample_schema_graph()
        retriever = SchemaRetriever(graph)
        tables = retriever.retrieve("user reviews with ratings", top_k=3)
        assert "reviews" in tables


# ---------------------------------------------------------------------------
# SQLGenerator tests (mocked LLM)
# ---------------------------------------------------------------------------


class TestSQLGenerator:
    """Test SQLGenerator with a mocked LLM."""

    def test_generate_returns_sql_query(self):
        mock_llm = MagicMock()
        structured_llm = MagicMock()
        structured_llm.invoke.return_value = SQLQuery(
            query="SELECT u.id, u.name FROM users u WHERE u.name = :name",
            parameters={"name": "alice"},
        )
        mock_llm.with_structured_output.return_value = structured_llm

        from teshq.core.sql_gen import SQLGenerator

        gen = SQLGenerator(mock_llm, provider="google")
        plan = QueryPlan(tables=["users"], filters=["name = alice"], aggregations=[], joins_needed=[])
        result = gen.generate("find user alice", "TABLE users(id PK, name TEXT)", plan)

        assert result.query == "SELECT u.id, u.name FROM users u WHERE u.name = :name"
        assert result.parameters == {"name": "alice"}

    def test_generate_with_error_hint(self):
        mock_llm = MagicMock()
        structured_llm = MagicMock()
        structured_llm.invoke.return_value = SQLQuery(
            query="SELECT id, name FROM users",
            parameters={},
        )
        mock_llm.with_structured_output.return_value = structured_llm

        from teshq.core.sql_gen import SQLGenerator

        gen = SQLGenerator(mock_llm, provider="google")
        plan = QueryPlan(tables=["users"], filters=[], aggregations=[], joins_needed=[])
        result = gen.generate(
            "list users",
            "TABLE users(id PK, name TEXT)",
            plan,
            error_hint="no such column: foo",
        )

        assert result.query == "SELECT id, name FROM users"
        # Verify the error_hint was passed through (messages should include correction hint)
        call_args = structured_llm.invoke.call_args
        messages = call_args[0][0]
        assert any("no such column: foo" in str(m) for m in messages)

    def test_azure_provider_invokes_plain_llm(self):
        """Azure path should not use with_structured_output."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"query": "SELECT 1", "parameters": {}}'
        plain_llm = MagicMock()
        plain_llm.invoke.return_value = mock_response
        mock_llm.bind.return_value = plain_llm

        from teshq.core.sql_gen import SQLGenerator

        gen = SQLGenerator(mock_llm, provider="azure")
        plan = QueryPlan(tables=["t"], filters=[], aggregations=[], joins_needed=[])
        result = gen.generate("test", "TABLE t(id PK)", plan)

        assert result.query == "SELECT 1"
        plain_llm.invoke.assert_called_once()


# ---------------------------------------------------------------------------
# Integration: Retriever → compressed schema → SQLGenerator
# ---------------------------------------------------------------------------


class TestRetrieverGeneratorIntegration:
    """Test the handoff from retriever to SQL generator."""

    def test_retriever_output_feeds_generator(self):
        graph = _sample_schema_graph()
        retriever = SchemaRetriever(graph)
        tables = retriever.retrieve("orders total revenue", top_k=3)
        compressed = graph.compressed_schema(tables)

        # Verify compressed schema contains the retrieved tables
        assert "orders" in compressed
        # The schema should be a non-empty string suitable for LLM consumption
        assert len(compressed) > 0
        assert "TABLE" in compressed
