"""
Tests for SchemaGraph with schema-qualified table names and dynamic compression.

Verifies that SchemaGraph correctly handles:
- schema-qualified table names (e.g. 'hr.employees', 'fin.transactions')
- the new `dialect` field
- `get_table_columns()` method
- Level 2 compression without hardcoded business column assumptions
"""

import pytest
from teshq.core.schema_graph import SchemaGraph, JoinEdge


def _make_schema_info(tables: dict, explicit_rels=None, dialect="SQLite"):
    """Helper to build a schema_info dict like introspect_db() returns."""
    si = {"tables": {}, "relationships": {"explicit": explicit_rels or [], "implicit": []}, "dialect": dialect}
    for tname, cols_and_fks in tables.items():
        columns = cols_and_fks.get("columns", [])
        pks = cols_and_fks.get("pks", [])
        fks = cols_and_fks.get("fks", [])
        si["tables"][tname] = {
            "columns": [{"name": c[0], "type": c[1], "nullable": True, "default": None, "is_primary_key": c[0] in pks, "comment": ""} for c in columns],
            "primary_keys": pks,
            "foreign_keys": fks,
            "indexes": [],
            "sample_data": [],
            "row_count": 0,
            "description": "",
        }
    return si


class TestSchemaGraphQualified:
    """Tests for schema-qualified table support."""

    def test_from_introspected_preserves_qualified_names(self):
        schema_info = _make_schema_info({
            "hr.employees": {
                "columns": [("emp_id", "INTEGER"), ("emp_name", "VARCHAR(100)"), ("dept_id", "INTEGER")],
                "pks": ["emp_id"],
                "fks": [{"constrained_columns": ["dept_id"], "referred_table": "hr.departments", "referred_columns": ["dept_id"], "name": "fk_dept"}],
            },
            "hr.departments": {
                "columns": [("dept_id", "INTEGER"), ("dept_name", "VARCHAR(100)")],
                "pks": ["dept_id"],
                "fks": [],
            },
        }, dialect="PostgreSQL")

        graph = SchemaGraph.from_introspected(schema_info)
        assert "hr.employees" in graph.tables
        assert "hr.departments" in graph.tables
        assert graph.dialect == "PostgreSQL"

    def test_compressed_schema_with_qualified_names(self):
        schema_info = _make_schema_info({
            "fin.transactions": {
                "columns": [("txn_id", "INTEGER"), ("acct_id", "INTEGER"), ("txn_amt", "DECIMAL(10,2)"), ("txn_dt", "DATE")],
                "pks": ["txn_id"],
                "fks": [{"constrained_columns": ["acct_id"], "referred_table": "fin.accounts", "referred_columns": ["acct_id"], "name": "fk_acct"}],
            },
            "fin.accounts": {
                "columns": [("acct_id", "INTEGER"), ("acct_name", "VARCHAR(100)"), ("acct_bal", "DECIMAL(10,2)")],
                "pks": ["acct_id"],
                "fks": [],
            },
        }, dialect="PostgreSQL")

        graph = SchemaGraph.from_introspected(schema_info)
        compressed = graph.compressed_schema(["fin.transactions", "fin.accounts"])
        assert "TABLE fin.transactions" in compressed
        assert "TABLE fin.accounts" in compressed
        assert "fin.transactions.acct_id" in compressed  # In JOINS section

    def test_get_table_columns(self):
        schema_info = _make_schema_info({
            "hr.employees": {
                "columns": [("emp_id", "INTEGER"), ("emp_name", "VARCHAR(100)"), ("salary", "DECIMAL(10,2)")],
                "pks": ["emp_id"],
                "fks": [],
            },
        })
        graph = SchemaGraph.from_introspected(schema_info)
        cols = graph.get_table_columns("hr.employees")
        assert cols == ["emp_id", "emp_name", "salary"]

    def test_get_table_columns_missing_table(self):
        graph = SchemaGraph(tables={}, joins=[], summary="", dialect="generic")
        assert graph.get_table_columns("nonexistent") == []

    def test_dialect_defaults_to_generic(self):
        schema_info = _make_schema_info({"users": {
            "columns": [("id", "INTEGER")],
            "pks": ["id"],
            "fks": [],
        }})
        # Remove dialect key to test default
        del schema_info["dialect"]
        graph = SchemaGraph.from_introspected(schema_info)
        assert graph.dialect == "generic"


class TestSchemaGraphDynamicCompression:
    """Tests for Level 2 compression without hardcoded business column names."""

    def _make_large_schema(self):
        """Create a schema with non-FMCG column names that would fail with hardcoded hints."""
        return _make_schema_info({
            "tickets": {
                "columns": [
                    ("ticket_id", "INTEGER"),
                    ("assignee_id", "INTEGER"),
                    ("priority", "VARCHAR(10)"),
                    ("severity", "VARCHAR(10)"),
                    ("resolution_time_hrs", "REAL"),
                    ("sla_breach", "BOOLEAN"),
                    ("opened_at", "TIMESTAMP"),
                    ("closed_at", "TIMESTAMP"),
                    ("summary_text", "TEXT"),
                    ("category_code", "VARCHAR(20)"),
                    ("subcategory", "VARCHAR(50)"),
                    ("customer_satisfaction_score", "REAL"),
                    ("escalation_level", "INTEGER"),
                    ("channel", "VARCHAR(20)"),
                ],
                "pks": ["ticket_id"],
                "fks": [{"constrained_columns": ["assignee_id"], "referred_table": "agents", "referred_columns": ["agent_id"], "name": "fk_agent"}],
            },
            "agents": {
                "columns": [
                    ("agent_id", "INTEGER"),
                    ("agent_name", "VARCHAR(100)"),
                    ("team", "VARCHAR(50)"),
                    ("skill_level", "INTEGER"),
                ],
                "pks": ["agent_id"],
                "fks": [],
            },
        })

    def test_level2_with_query_words_keeps_relevant_cols(self):
        schema_info = self._make_large_schema()
        graph = SchemaGraph.from_introspected(schema_info)

        # Force very tight budget to trigger Level 2
        result = graph.compressed_schema_within_budget(
            ["tickets", "agents"],
            max_tokens=10,  # Very small to force Level 2
            query_words={"resolution", "time", "priority"},
        )

        # Should keep PK/FK columns and columns matching query words
        assert "ticket_id" in result  # PK
        assert "assignee_id" in result  # FK
        # "resolution_time_hrs" splits to {"resolution", "time", "hrs"} which matches query words
        assert "resolution_time_hrs" in result
        assert "priority" in result

    def test_level2_without_query_words_uses_fallback_patterns(self):
        schema_info = self._make_large_schema()
        graph = SchemaGraph.from_introspected(schema_info)

        # Without query_words, falls back to generic pattern matching
        result = graph.compressed_schema_within_budget(
            ["tickets", "agents"],
            max_tokens=10,
        )
        # PKs and FKs should always be present
        assert "ticket_id" in result
        assert "assignee_id" in result

    def test_level2_non_standard_columns_not_lost(self):
        """Ensure columns like 'emp_salary_amt' or 'txn_dt' are discoverable via query words."""
        schema_info = _make_schema_info({
            "payroll": {
                "columns": [
                    ("emp_id", "INTEGER"),
                    ("emp_salary_amt", "DECIMAL(10,2)"),
                    ("pay_period_dt", "DATE"),
                    ("deduction_pct", "REAL"),
                    ("bonus_indicator", "BOOLEAN"),
                    ("dept_code", "VARCHAR(10)"),
                    ("tax_bracket", "VARCHAR(5)"),
                    ("ytd_earnings", "DECIMAL(12,2)"),
                ],
                "pks": ["emp_id"],
                "fks": [],
            },
        })
        graph = SchemaGraph.from_introspected(schema_info)

        result = graph.compressed_schema_within_budget(
            ["payroll"],
            max_tokens=5,
            query_words={"salary", "bonus"},
        )
        assert "emp_salary_amt" in result
        assert "bonus_indicator" in result

    def test_neighbors_with_qualified_names(self):
        schema_info = _make_schema_info({
            "hr.employees": {
                "columns": [("emp_id", "INTEGER"), ("dept_id", "INTEGER")],
                "pks": ["emp_id"],
                "fks": [{"constrained_columns": ["dept_id"], "referred_table": "hr.departments", "referred_columns": ["dept_id"]}],
            },
            "hr.departments": {
                "columns": [("dept_id", "INTEGER"), ("dept_name", "VARCHAR(100)")],
                "pks": ["dept_id"],
                "fks": [],
            },
        })
        graph = SchemaGraph.from_introspected(schema_info)
        neighbors = graph.neighbors("hr.employees")
        assert "hr.departments" in neighbors
