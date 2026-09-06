"""
Tests for dialect-aware SQL validation.

Verifies that validate_sql() accepts the optional dialect parameter and
that dialect-specific keywords (TOP, ROWNUM, ILIKE, etc.) are not rejected.
"""

import pytest
from teshq.core.sql_validator import validate_sql
from teshq.core.validation import ValidationError


class TestDialectAwareValidation:
    """Verify that validate_sql accepts dialect and doesn't reject dialect-specific syntax."""

    def test_accepts_dialect_param_sqlite(self):
        """validate_sql should accept dialect='SQLite' without errors for valid SQL."""
        validate_sql("SELECT id, name FROM users WHERE id = 1", dialect="SQLite")

    def test_accepts_dialect_param_postgresql(self):
        validate_sql("SELECT id, name FROM users WHERE name ILIKE '%john%'", dialect="PostgreSQL")

    def test_accepts_dialect_param_mysql(self):
        validate_sql("SELECT id, name FROM users WHERE id = 1", dialect="MySQL")

    def test_accepts_dialect_param_mssql(self):
        validate_sql("SELECT TOP 10 id, name FROM users WHERE id = 1", dialect="SQL Server (T-SQL)")

    def test_accepts_dialect_param_oracle(self):
        validate_sql("SELECT id, name FROM users WHERE ROWNUM <= 10", dialect="Oracle")

    def test_accepts_dialect_param_none(self):
        """dialect=None (default) should work exactly as before."""
        validate_sql("SELECT id, name FROM users WHERE id = 1")

    # --- Dialect-specific functions that must NOT be rejected ---

    def test_postgresql_ilike(self):
        validate_sql(
            "SELECT id, name FROM products WHERE name ILIKE '%widget%'",
            dialect="PostgreSQL",
        )

    def test_postgresql_current_date(self):
        validate_sql(
            "SELECT id, created_at FROM orders WHERE created_at >= CURRENT_DATE",
            dialect="PostgreSQL",
        )

    def test_postgresql_date_part(self):
        validate_sql(
            "SELECT id, DATE_PART('year', created_at) AS yr FROM orders WHERE id > 0",
            dialect="PostgreSQL",
        )

    def test_mssql_top(self):
        validate_sql(
            "SELECT TOP 5 id, name FROM customers WHERE status = 'active'",
            dialect="SQL Server (T-SQL)",
        )

    def test_mssql_getdate(self):
        validate_sql(
            "SELECT id, name FROM events WHERE event_date < GETDATE()",
            dialect="SQL Server (T-SQL)",
        )

    def test_mssql_datediff(self):
        validate_sql(
            "SELECT id, DATEDIFF(day, start_date, end_date) AS duration FROM tasks WHERE id > 0",
            dialect="SQL Server (T-SQL)",
        )

    def test_oracle_rownum(self):
        validate_sql(
            "SELECT id, name FROM employees WHERE ROWNUM <= 10",
            dialect="Oracle",
        )

    def test_oracle_sysdate(self):
        validate_sql(
            "SELECT id, name FROM orders WHERE order_date > SYSDATE - 30",
            dialect="Oracle",
        )

    def test_oracle_nvl(self):
        validate_sql(
            "SELECT id, NVL(discount, 0) AS discount FROM line_items WHERE id > 0",
            dialect="Oracle",
        )

    def test_mysql_curdate(self):
        validate_sql(
            "SELECT id, name FROM users WHERE created_at >= CURDATE()",
            dialect="MySQL",
        )

    def test_mysql_datediff(self):
        validate_sql(
            "SELECT id, DATEDIFF(end_date, start_date) AS duration FROM projects WHERE id > 0",
            dialect="MySQL",
        )

    def test_sqlite_julianday(self):
        validate_sql(
            "SELECT id, CAST(julianday(date2) - julianday(date1) AS INTEGER) AS diff FROM orders WHERE id > 0",
            dialect="SQLite",
        )

    def test_sqlite_strftime(self):
        validate_sql(
            "SELECT id, strftime('%Y', created_at) AS yr FROM orders WHERE id > 0",
            dialect="SQLite",
        )

    # --- Schema-qualified references must pass validation ---

    def test_schema_qualified_table(self):
        """schema.table references should not be rejected."""
        validate_sql(
            "SELECT e.id, e.name FROM hr.employees e WHERE e.id > 0",
            dialect="PostgreSQL",
        )

    def test_schema_qualified_three_part(self):
        """schema.table.column references should not be rejected."""
        validate_sql(
            "SELECT hr.employees.id, hr.employees.name FROM hr.employees WHERE hr.employees.id > 0",
            dialect="PostgreSQL",
        )

    # --- Destructive statements should still be blocked regardless of dialect ---

    def test_drop_still_blocked_with_dialect(self):
        with pytest.raises(ValidationError):
            validate_sql("DROP TABLE users", dialect="PostgreSQL")

    def test_truncate_still_blocked_with_dialect(self):
        with pytest.raises(ValidationError):
            validate_sql("TRUNCATE TABLE orders", dialect="MySQL")

    def test_select_star_still_blocked_with_dialect(self):
        with pytest.raises(ValidationError):
            validate_sql("SELECT * FROM users", dialect="SQLite")

    def test_delete_without_where_still_blocked(self):
        with pytest.raises(ValidationError):
            validate_sql("DELETE FROM users", dialect="Oracle")

    def test_positional_params_still_blocked(self):
        with pytest.raises(ValidationError):
            validate_sql("SELECT id FROM users WHERE id = ?", dialect="SQLite")
