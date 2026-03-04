"""
Integration tests for the TeshEngine (2-stage AI SQL Compiler).
"""

import os
import pytest
from sqlalchemy import create_engine, text

from teshq.core.engine import TeshEngine
from teshq.core.models import QueryResult

# Mock the LLM factory builds to avoid actual API calls during CI/CD
class MockPlanner:
    def plan(self, nl_query, schema_str):
        from teshq.core.models import QueryPlan
        return QueryPlan(
            tables=["users"],
            filters=["none"],
            aggregations=["count"],
            joins_needed=[]
        )

class MockSQLGen:
    def generate(self, nl_query, schema_str, plan):
        from teshq.core.models import SQLQuery
        return SQLQuery(
            query="SELECT COUNT(*) as count FROM users",
            parameters={},
            explanation="Counts all users."
        )

@pytest.fixture
def mock_engine_llm(monkeypatch):
    """Mocks the LLM builders to prevent API calls."""
    import teshq.core.engine
    monkeypatch.setattr(teshq.core.engine, "build_planner", lambda **kw: MockPlanner())
    monkeypatch.setattr(teshq.core.engine, "build_sql_generator", lambda **kw: MockSQLGen())

@pytest.fixture
def test_db_url(tmp_path):
    """Create a temporary SQLite database with sample data."""
    db_file = tmp_path / "test.db"
    db_url = f"sqlite:///{db_file}"
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE
            );
        """))
        conn.execute(text("INSERT INTO users (name, email) VALUES ('Alice', 'alice@example.com')"))
        conn.execute(text("INSERT INTO users (name, email) VALUES ('Bob', 'bob@example.com')"))
    return db_url

def test_tesh_engine_end_to_end(mock_engine_llm, test_db_url):
    """
    Test the full 2-stage engine pipeline:
    Introspect -> Prune -> Plan -> Generate -> Validate -> Normalize -> Execute -> Return.
    """
    engine = TeshEngine(
        db_url=test_db_url,
        provider="google",
        api_key="mock_key",
        model_name="mock_model"
    )

    result = engine.query("How many users are there?", dry_run=False)

    print(result)

    assert result.success is True
    assert result.error is None
    assert result.sql == "SELECT COUNT(*) AS COUNT\nFROM users"
    
    # 2 rows were inserted, so count is 2
    assert len(result.rows) == 1
    assert result.rows[0]["COUNT"] == 2
    
    assert result.plan is not None
    assert result.plan.tables == ["users"]
    
    assert result.plan_latency_ms >= 0
    assert result.sql_latency_ms >= 0
    assert result.exec_latency_ms >= 0
    
    # Check that schema was successfully extracted from SQLite
    assert "users" in result.schema_preview.lower()

def test_tesh_engine_dry_run(mock_engine_llm, test_db_url):
    """Test that dry_run=True skips execution and returns empty rows."""
    engine = TeshEngine(
        db_url=test_db_url,
        provider="google",
        api_key="mock_key",
        model_name="mock_model"
    )

    result = engine.query("How many users are there?", dry_run=True)

    assert result.success is True
    assert result.dry_run is True
    assert len(result.rows) == 0  # No execution happened
    assert result.sql == "SELECT COUNT(*) AS COUNT\nFROM users"
