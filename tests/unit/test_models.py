"""Unit tests for teshq.core.models (no I/O, no DB)."""

import pytest
from teshq.core.models import (
    ColumnInfo,
    QueryResult,
    SQLQuery,
    SchemaInfo,
    TableInfo,
)


class TestSQLQuery:
    def test_basic_construction(self):
        q = SQLQuery(query="SELECT 1", parameters={})
        assert q.query == "SELECT 1"
        assert q.parameters == {}

    def test_is_read_only_true(self):
        q = SQLQuery(query="SELECT * FROM users", parameters={})
        assert q.is_read_only() is True

    def test_is_read_only_false(self):
        q = SQLQuery(query="INSERT INTO users VALUES (:id)", parameters={"id": 1})
        assert q.is_read_only() is False

    def test_default_parameters(self):
        q = SQLQuery(query="SELECT 1")
        assert q.parameters == {}


class TestTableInfo:
    def test_compressed_repr_primary_key(self):
        table = TableInfo(
            name="users",
            columns=[
                ColumnInfo(name="id", type="INT", primary_key=True, nullable=False),
                ColumnInfo(name="name", type="TEXT", nullable=False),
            ],
        )
        result = table.compressed_repr()
        assert "TABLE users" in result
        assert "id INT PK NN" in result
        assert "name TEXT NN" in result

    def test_compressed_repr_foreign_key(self):
        table = TableInfo(
            name="orders",
            columns=[
                ColumnInfo(name="user_id", type="INT", foreign_key="users.id", nullable=False),
            ],
        )
        result = table.compressed_repr()
        assert "FK→users.id" in result


class TestSchemaInfo:
    def test_to_compressed_text(self):
        schema = SchemaInfo(
            database_name="mydb",
            dialect="postgresql",
            tables={
                "users": TableInfo(
                    name="users",
                    columns=[ColumnInfo(name="id", type="INT", primary_key=True, nullable=False)],
                )
            },
        )
        text = schema.to_compressed_text()
        assert "mydb" in text
        assert "TABLE users" in text

    def test_empty_schema(self):
        schema = SchemaInfo()
        text = schema.to_compressed_text()
        assert text == ""


class TestQueryResult:
    def test_total_tokens(self):
        r = QueryResult(sql="SELECT 1", prompt_tokens=100, completion_tokens=50)
        assert r.total_tokens == 150

    def test_is_empty(self):
        r = QueryResult(sql="SELECT 1", rows=[], row_count=0)
        assert r.is_empty() is True

    def test_cost_estimate_positive(self):
        r = QueryResult(sql="SELECT 1", prompt_tokens=1000, completion_tokens=200)
        assert r.cost_estimate_usd > 0
