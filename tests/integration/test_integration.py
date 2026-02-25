"""
Integration tests using a real SQLite database.

Tests join queries, group by, filtering, aggregation, and multi-table joins.
No external DB allowed — SQLite only.
"""

import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from teshq.core.models import QueryPlan, SQLQuery
from teshq.core.query import execute_sql_query
from teshq.core.schema_graph import SchemaGraph
from teshq.core.schema_pruner import prune_schema
from teshq.core.sql_normalizer import normalize_sql
from teshq.core.sql_validator import validate_sql


# ---------------------------------------------------------------------------
# Fixture: temporary SQLite database with test data
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sqlite_db_url(tmp_path_factory):
    """Create a SQLite DB with users, orders, products, order_items."""
    db_dir = tmp_path_factory.mktemp("db")
    db_path = db_dir / "test.db"

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL NOT NULL
        );

        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            total REAL NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY,
            order_id INTEGER NOT NULL REFERENCES orders(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            qty INTEGER NOT NULL
        );

        INSERT INTO users VALUES (1, 'Alice', 'alice@example.com', 1);
        INSERT INTO users VALUES (2, 'Bob', 'bob@example.com', 1);
        INSERT INTO users VALUES (3, 'Charlie', 'charlie@example.com', 0);

        INSERT INTO products VALUES (1, 'Widget', 9.99);
        INSERT INTO products VALUES (2, 'Gadget', 24.99);

        INSERT INTO orders VALUES (1, 1, 19.98, '2024-01-01');
        INSERT INTO orders VALUES (2, 1, 24.99, '2024-01-05');
        INSERT INTO orders VALUES (3, 2, 9.99, '2024-01-10');

        INSERT INTO order_items VALUES (1, 1, 1, 2);
        INSERT INTO order_items VALUES (2, 2, 2, 1);
        INSERT INTO order_items VALUES (3, 3, 1, 1);
    """)
    conn.commit()
    conn.close()

    return f"sqlite:///{db_path}"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def run(db_url: str, sql: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    validate_sql(sql)
    normalized = normalize_sql(sql)
    return execute_sql_query(db_url=db_url, query=normalized, parameters=params or {})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSimpleSelect:
    def test_select_all_users(self, sqlite_db_url):
        rows = run(sqlite_db_url, "SELECT id, name, email FROM users")
        assert len(rows) == 3

    def test_filter_active_users(self, sqlite_db_url):
        rows = run(sqlite_db_url, "SELECT id, name FROM users WHERE active = :active", {"active": 1})
        assert len(rows) == 2
        names = [r["name"] for r in rows]
        assert "Alice" in names
        assert "Bob" in names
        assert "Charlie" not in names


class TestJoinQueries:
    def test_user_orders_join(self, sqlite_db_url):
        sql = (
            "SELECT u.name, o.total "
            "FROM users u "
            "JOIN orders o ON u.id = o.user_id "
            "ORDER BY o.id"
        )
        rows = run(sqlite_db_url, sql)
        assert len(rows) == 3
        assert rows[0]["name"] == "Alice"

    def test_multi_table_join(self, sqlite_db_url):
        sql = (
            "SELECT u.name, p.name AS product, oi.qty "
            "FROM users u "
            "JOIN orders o ON u.id = o.user_id "
            "JOIN order_items oi ON o.id = oi.order_id "
            "JOIN products p ON oi.product_id = p.id "
            "ORDER BY u.id, p.id"
        )
        rows = run(sqlite_db_url, sql)
        assert len(rows) == 3


class TestAggregation:
    def test_count_orders_per_user(self, sqlite_db_url):
        sql = (
            "SELECT u.name, COUNT(o.id) AS order_count "
            "FROM users u "
            "JOIN orders o ON u.id = o.user_id "
            "GROUP BY u.id, u.name "
            "ORDER BY u.id"
        )
        rows = run(sqlite_db_url, sql)
        assert len(rows) == 2  # Charlie has no orders
        alice_row = next(r for r in rows if r["name"] == "Alice")
        assert alice_row["order_count"] == 2

    def test_total_revenue_per_user(self, sqlite_db_url):
        sql = (
            "SELECT u.name, SUM(o.total) AS revenue "
            "FROM users u "
            "JOIN orders o ON u.id = o.user_id "
            "GROUP BY u.id, u.name "
            "ORDER BY revenue DESC"
        )
        rows = run(sqlite_db_url, sql)
        assert rows[0]["name"] == "Alice"
        assert abs(rows[0]["revenue"] - 44.97) < 0.01

    def test_group_by_with_having(self, sqlite_db_url):
        sql = (
            "SELECT u.name, COUNT(o.id) AS cnt "
            "FROM users u "
            "JOIN orders o ON u.id = o.user_id "
            "GROUP BY u.id, u.name "
            "HAVING COUNT(o.id) > :min_orders"
        )
        rows = run(sqlite_db_url, sql, {"min_orders": 1})
        assert len(rows) == 1
        assert rows[0]["name"] == "Alice"


class TestSchemaGraphIntegration:
    def test_schema_graph_from_introspect(self, sqlite_db_url):
        from teshq.core.introspect import introspect_db

        schema_info = introspect_db(db_url=sqlite_db_url)
        graph = SchemaGraph.from_introspected(schema_info)

        assert "users" in graph.tables
        assert "orders" in graph.tables
        assert "products" in graph.tables
        assert "order_items" in graph.tables

    def test_prune_finds_orders_and_users(self, sqlite_db_url):
        from teshq.core.introspect import introspect_db

        schema_info = introspect_db(db_url=sqlite_db_url)
        graph = SchemaGraph.from_introspected(schema_info)

        selected = prune_schema(graph, "show orders placed by each user")
        assert "orders" in selected

    def test_compressed_schema_format(self, sqlite_db_url):
        from teshq.core.introspect import introspect_db

        schema_info = introspect_db(db_url=sqlite_db_url)
        graph = SchemaGraph.from_introspected(schema_info)
        compressed = graph.compressed_schema(["users", "orders"])

        assert "TABLE users" in compressed
        assert "TABLE orders" in compressed
