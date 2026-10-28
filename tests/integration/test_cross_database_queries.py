"""
Integration tests for Cross-Database Query Execution and Named Multi-Database Isolation.

Uses the primary ecommerce fixture at testing/databases/ecommerce.sqlite alongside
isolated, temporary SQLite databases for analytics and finance fixtures.
"""

import sqlite3
import tempfile
import threading
from pathlib import Path
from typing import Generator

import pandas as pd
import pytest

from teshq.api import TeshQuery
from teshq.core.connection import connection_manager
from teshq.core.federation import (
    CrossDatabaseOrchestrator,
    CrossDatabasePlan,
    SubquerySpec,
)


ECOMMERCE_DB_PATH = Path(__file__).resolve().parent.parent.parent / "testing" / "databases" / "ecommerce.sqlite"


@pytest.fixture(scope="module")
def ecommerce_db() -> str:
    """Ensure the ecommerce testing database exists and return its URL."""
    if not ECOMMERCE_DB_PATH.exists():
        pytest.skip(f"Ecommerce database not found at {ECOMMERCE_DB_PATH}. Run create_database.py.")
    return f"sqlite:///{ECOMMERCE_DB_PATH}"


@pytest.fixture
def temp_analytics_db() -> Generator[str, None, None]:
    """Create an isolated, temporary analytics SQLite database with monthly ledger data."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        temp_path = Path(f.name)

    conn = sqlite3.connect(str(temp_path))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE ledger_monthly_revenue (
            fiscal_month VARCHAR(7) PRIMARY KEY,
            recognized_revenue NUMERIC(14, 2) NOT NULL,
            audit_status VARCHAR(20) DEFAULT 'certified'
        );
    """)
    cursor.execute("""
        CREATE TABLE shared_metadata (
            metadata_key VARCHAR(50) PRIMARY KEY,
            analytics_value VARCHAR(100) NOT NULL
        );
    """)

    sample_ledger = [
        ("2024-01", 1250000.00, "certified"),
        ("2024-02", 1320000.00, "certified"),
        ("2024-03", 1450000.00, "certified"),
        ("2024-04", 1280000.00, "in_review"),
        ("2024-05", 1520000.00, "certified"),
        ("2024-06", 1610000.00, "certified"),
    ]
    cursor.executemany("INSERT INTO ledger_monthly_revenue VALUES (?, ?, ?);", sample_ledger)
    cursor.execute("INSERT INTO shared_metadata VALUES ('data_source', 'analytics_warehouse');")
    conn.commit()
    conn.close()

    db_url = f"sqlite:///{temp_path}"
    try:
        yield db_url
    finally:
        if temp_path.exists():
            temp_path.unlink()


@pytest.fixture
def temp_finance_db() -> Generator[str, None, None]:
    """Create another temporary database sharing a table name with different columns."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        temp_path = Path(f.name)

    conn = sqlite3.connect(str(temp_path))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE shared_metadata (
            metadata_key VARCHAR(50) PRIMARY KEY,
            finance_balance NUMERIC(12, 2) NOT NULL,
            currency VARCHAR(3) DEFAULT 'USD'
        );
    """)
    cursor.execute("INSERT INTO shared_metadata VALUES ('data_source', 987654.32, 'USD');")
    conn.commit()
    conn.close()

    db_url = f"sqlite:///{temp_path}"
    try:
        yield db_url
    finally:
        if temp_path.exists():
            temp_path.unlink()


class MockPlanner:
    def plan(self, nl_query, schema_str, callbacks=None, **kwargs):
        from teshq.core.models import QueryPlan
        return QueryPlan(tables=["customers", "products"], filters=[], aggregations=[], joins_needed=[])


class MockSQLGen:
    def generate(self, nl_query, schema_str, plan, error_hint=None, callbacks=None, **kwargs):
        from teshq.core.models import SQLQuery
        query = nl_query if nl_query.strip().upper().startswith("SELECT") else "SELECT COUNT(*) AS count FROM customers;"
        return SQLQuery(query=query, parameters={}, explanation="Test SQL")


@pytest.fixture(autouse=True)
def mock_engine_llm(monkeypatch):
    """Mocks the LLM builders to prevent API calls and resets connection manager."""
    import teshq.core.engine
    monkeypatch.setattr(teshq.core.engine, "build_planner", lambda **kw: MockPlanner())
    monkeypatch.setattr(teshq.core.engine, "build_sql_generator", lambda **kw: MockSQLGen())
    connection_manager.clear_all()
    yield
    connection_manager.clear_all()


class TestMultiDatabaseQueryRouting:
    """Test registering multiple named databases and executing independent queries."""

    def test_query_primary_ecommerce_database(self, ecommerce_db):
        client = TeshQuery(db_url=ecommerce_db, gemini_api_key="mock_key_for_test")
        df = client.query_df(
            "SELECT COUNT(*) AS total_customers FROM customers;",
            connection=None
        )
        assert len(df) == 1
        assert df.iloc[0]["total_customers"] >= 10000

    def test_register_and_query_named_connections(self, ecommerce_db, temp_analytics_db):
        client = TeshQuery(gemini_api_key="mock_key_for_test")
        client.add_connection(name="ecommerce", db_url=ecommerce_db)
        client.add_connection(name="analytics", db_url=temp_analytics_db)

        # Query ecommerce via named connection
        df_ecom = client.query_df("SELECT COUNT(*) AS n_products FROM products;", connection="ecommerce")
        assert df_ecom.iloc[0]["n_products"] >= 5000

        # Query analytics via named connection
        df_fin = client.query_df(
            "SELECT COUNT(*) AS n_ledger FROM ledger_monthly_revenue;",
            connection="analytics"
        )
        assert df_fin.iloc[0]["n_ledger"] == 6

    def test_schema_collision_isolation_same_table_name(self, temp_analytics_db, temp_finance_db):
        """Verify two databases with the same table name ('shared_metadata') do not collide."""
        client = TeshQuery(gemini_api_key="mock_key")
        client.add_connection(name="analytics_meta", db_url=temp_analytics_db)
        client.add_connection(name="finance_meta", db_url=temp_finance_db)

        df_analytics = client.query_df(
            "SELECT metadata_key, analytics_value FROM shared_metadata;",
            connection="analytics_meta"
        )
        assert "analytics_value" in df_analytics.columns
        assert "finance_balance" not in df_analytics.columns

        df_finance = client.query_df(
            "SELECT metadata_key, finance_balance FROM shared_metadata;",
            connection="finance_meta"
        )
        assert "finance_balance" in df_finance.columns
        assert "analytics_value" not in df_finance.columns

    def test_invalid_connection_name_produces_clear_error(self, ecommerce_db):
        client = TeshQuery(gemini_api_key="mock_key")
        client.add_connection(name="ecommerce", db_url=ecommerce_db)

        with pytest.raises(KeyError, match="not found"):
            client.query_df("SELECT 1;", connection="unknown_db")


class TestCrossDatabaseFederation:
    """Test federated multi-subquery planning, execution, and bounded merging."""

    def test_cross_database_monthly_revenue_reconciliation(self, ecommerce_db, temp_analytics_db):
        orchestrator = CrossDatabaseOrchestrator(max_rows_per_subquery=100)

        plan = CrossDatabasePlan(
            plan_id="plan_monthly_recon",
            query_text="Compare monthly ecommerce GMV against finance recognized revenue",
            subqueries=[
                SubquerySpec(
                    connection_name="ecommerce",
                    sql=(
                        "SELECT strftime('%Y-%m', order_date) AS month, "
                        "ROUND(SUM(total_amount), 2) AS ecom_gmv "
                        "FROM orders GROUP BY month ORDER BY month;"
                    ),
                    alias="ecom"
                ),
                SubquerySpec(
                    connection_name="analytics",
                    sql=(
                        "SELECT fiscal_month AS month, recognized_revenue AS fin_rev, audit_status "
                        "FROM ledger_monthly_revenue ORDER BY month;"
                    ),
                    alias="fin"
                )
            ],
            join_key="month",
            join_type="inner",
        )

        # Register connections in connection_manager
        connection_manager.add_connection("ecommerce", ecommerce_db, overwrite=True)
        connection_manager.add_connection("analytics", temp_analytics_db, overwrite=True)

        # Validate plan
        is_valid, validation_errors = orchestrator.validate_plan(plan)
        assert is_valid is True
        assert not validation_errors

        # Execute plan
        result = orchestrator.execute_plan(plan)
        assert result.plan_id == "plan_monthly_recon"
        assert result.status == "success"
        assert not result.partial_failure
        assert len(result.rows) > 0

        # Check source attribution and columns
        first_row = result.rows[0]
        assert "month" in first_row
        assert "ecom_gmv" in first_row or "ecommerce_ecom_gmv" in first_row
        assert "fin_rev" in first_row or "analytics_fin_rev" in first_row

        assert "ecommerce" in result.source_attribution
        assert "analytics" in result.source_attribution

    def test_cross_database_dry_run_executes_no_sql(self, ecommerce_db, temp_analytics_db):
        orchestrator = CrossDatabaseOrchestrator()
        plan = CrossDatabasePlan(
            plan_id="dry_run_plan",
            query_text="Dry run check",
            subqueries=[
                SubquerySpec(connection_name="ecommerce", sql="SELECT 1 AS val;", alias="e1"),
                SubquerySpec(connection_name="analytics", sql="SELECT 2 AS val;", alias="a1"),
            ],
            join_key="val",
            join_type="inner",
        )

        result = orchestrator.execute_plan(plan, dry_run=True)
        assert result.status == "dry_run"
        assert len(result.rows) == 0
        assert len(result.subquery_results) == 2
        for sq in result.subquery_results:
            assert sq.rows_returned == 0
            assert sq.status == "dry_run"

    def test_cross_database_partial_failure_reporting(self, ecommerce_db):
        connection_manager.add_connection("ecommerce", ecommerce_db, overwrite=True)
        orchestrator = CrossDatabaseOrchestrator()
        plan = CrossDatabasePlan(
            plan_id="partial_fail_plan",
            query_text="Partial failure scenario",
            subqueries=[
                SubquerySpec(
                    connection_name="ecommerce",
                    sql="SELECT COUNT(*) AS cnt FROM products;",
                    alias="ecom"
                ),
                SubquerySpec(
                    connection_name="non_existent_connection",
                    sql="SELECT col1, col2 FROM missing_table;",
                    alias="missing"
                ),
            ],
            join_key="cnt",
            join_type="left",
        )

        result = orchestrator.execute_plan(plan)
        assert result.status == "partial_failure"
        assert result.partial_failure is True
        assert len(result.subquery_results) == 2

        # One succeeded, one explicitly reported error
        statuses = {s.connection_name: s.status for s in result.subquery_results}
        assert statuses["ecommerce"] == "success"
        assert "error" in statuses["non_existent_connection"]

    def test_security_policy_enforcement_on_subqueries(self):
        orchestrator = CrossDatabaseOrchestrator()
        destructive_plan = CrossDatabasePlan(
            plan_id="attack_plan",
            query_text="Drop tables",
            subqueries=[
                SubquerySpec(
                    connection_name="ecommerce",
                    sql="DROP TABLE customers;",
                    alias="bad"
                )
            ]
        )

        is_valid, errors = orchestrator.validate_plan(destructive_plan)
        assert is_valid is False
        assert any("destructive" in err.lower() or "drop" in err.lower() for err in errors)

    def test_null_values_and_duplicate_keys_handling(self):
        orchestrator = CrossDatabaseOrchestrator()
        # Test merging with duplicate join keys and missing nulls
        r1 = [
            {"k": "2024-01", "val1": 100},
            {"k": "2024-01", "val1": 150},  # duplicate key
            {"k": None, "val1": 50},        # null key
        ]
        r2 = [
            {"k": "2024-01", "val2": 200},
            {"k": "2024-02", "val2": 300},  # missing from r1
            {"k": None, "val2": 99},
        ]

        from teshq.core.federation import SubqueryExecutionResult
        sub_exec = [
            SubqueryExecutionResult(
                connection_name="c1", sql="", alias="t1", rows_returned=3,
                execution_time_ms=1.0, status="success", rows=r1
            ),
            SubqueryExecutionResult(
                connection_name="c2", sql="", alias="t2", rows_returned=3,
                execution_time_ms=1.0, status="success", rows=r2
            ),
        ]

        merged, sources = orchestrator._combine_result_sets(sub_exec, join_key="k", join_type="outer")
        assert len(merged) > 0
        assert "c1" in sources
        assert "c2" in sources

    def test_concurrent_queries_against_different_connections(self, ecommerce_db, temp_analytics_db):
        """Verify concurrent queries against separate connections execute in isolation without race conditions."""
        client = TeshQuery(gemini_api_key="mock_key")
        client.add_connection(name="ecom_thread", db_url=ecommerce_db)
        client.add_connection(name="fin_thread", db_url=temp_analytics_db)

        results = {}
        errors = []

        def worker_ecom():
            try:
                df = client.query_df("SELECT COUNT(*) AS c FROM products;", connection="ecom_thread")
                results["ecom"] = df.iloc[0]["c"]
            except Exception as e:
                errors.append(e)

        def worker_fin():
            try:
                df = client.query_df("SELECT COUNT(*) AS c FROM ledger_monthly_revenue;", connection="fin_thread")
                results["fin"] = df.iloc[0]["c"]
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=worker_ecom)
        t2 = threading.Thread(target=worker_fin)

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        assert not errors
        assert results["ecom"] >= 5000
        assert results["fin"] == 6

    def test_plan_query_infers_available_connections(self, ecommerce_db, temp_analytics_db):
        """Verify plan_query correctly resolves available connections without TypeError or AttributeError."""
        connection_manager.add_connection("ecommerce", ecommerce_db, overwrite=True)
        connection_manager.add_connection("analytics", temp_analytics_db, overwrite=True)
        orchestrator = CrossDatabaseOrchestrator()
        plan = orchestrator.plan_query("Compare regional and catalog performance")
        assert plan.nl_query == "Compare regional and catalog performance"
        assert len(plan.subqueries) >= 2
        assert all(isinstance(sq.database, str) and sq.database for sq in plan.subqueries)

    def test_combine_result_sets_preserves_none_join_keys(self):
        """Verify None/NULL join keys are not coerced to the string 'None'."""
        orchestrator = CrossDatabaseOrchestrator()
        df1 = pd.DataFrame([{"id": "1", "val1": "A"}, {"id": None, "val1": "B"}])
        df2 = pd.DataFrame([{"id": "1", "val2": "X"}, {"id": None, "val2": "Y"}])

        res, attr = orchestrator._combine_result_sets({"db1": df1, "db2": df2}, join_keys=["id"])
        # Check that the None row has NoneType id, not literal string 'None'
        none_rows = res[res["id"].isna() | (res["id"] == "None") | (res["id"] is None)]
        assert len(none_rows) > 0
        for val in none_rows["id"]:
            assert val is None or pd.isna(val)
            assert not isinstance(val, str)
