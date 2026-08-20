"""
Extended tests for the SQL validation layer.

Covers:
- Relaxed Gemini API key regex (Bug #3)
- AST-based DDL detection (obfuscated casing, embedded comments)
- %s false-positive regression (Bug from old regex-on-full-SQL approach)
- sqlparse-based DROP/TRUNCATE/ALTER detection
"""

import pytest

from teshq.core.validation import ConfigValidator, ValidationError
from teshq.core.sql_validator import validate_sql


# ---------------------------------------------------------------------------
# ConfigValidator — Gemini API key regex (relaxed in Bug #3 fix)
# ---------------------------------------------------------------------------


class TestGeminiApiKeyRegex:
    """Test the relaxed Gemini API key validation regex."""

    def _validate(self, key: str):
        """Call ConfigValidator.validate_gemini_api_key and return (bool, msg)."""
        return ConfigValidator.validate_gemini_api_key(key)

    def test_standard_39_char_key_passes(self):
        key = "AIza" + "A" * 35  # exactly 39 chars
        valid, msg = self._validate(key)
        assert valid, f"Expected valid but got: {msg}"

    def test_longer_key_passes(self):
        """Newer Google-issued keys are >39 chars."""
        key = "AIza" + "A" * 50  # 54 chars
        valid, msg = self._validate(key)
        assert valid, f"Expected valid but got: {msg}"

    def test_short_key_fails(self):
        key = "AIza" + "A" * 10  # too short
        valid, msg = self._validate(key)
        assert not valid

    def test_wrong_prefix_fails(self):
        key = "BADX" + "A" * 35
        valid, msg = self._validate(key)
        assert not valid

    def test_dashes_and_underscores_allowed(self):
        key = "AIza" + "A-_" * 12  # mixed dashes and underscores
        valid, msg = self._validate(key)
        assert valid, f"Expected valid but got: {msg}"

    def test_empty_key_fails(self):
        valid, msg = self._validate("")
        assert not valid

    def test_none_like_fails(self):
        valid, msg = self._validate("not-a-real-key")
        assert not valid


# ---------------------------------------------------------------------------
# SQL Validator — AST-based detection
# ---------------------------------------------------------------------------


class TestSqlValidatorAst:
    """Test that the AST-based validator catches obfuscated destructive SQL."""

    # ---- DROP ----

    def test_drop_table_blocked(self):
        with pytest.raises(ValidationError, match="DROP"):
            validate_sql("DROP TABLE users")

    def test_drop_mixed_case_blocked(self):
        """Regex-based validators could be bypassed with casing tricks."""
        with pytest.raises(ValidationError, match="DROP"):
            validate_sql("DrOp TABLE users")

    def test_drop_with_comment_blocked(self):
        """Embedding a comment between DROP and TABLE should still be caught."""
        with pytest.raises(ValidationError, match="DROP"):
            validate_sql("DROP /* skip */ TABLE users")

    # ---- TRUNCATE ----

    def test_truncate_blocked(self):
        with pytest.raises(ValidationError, match="TRUNCATE"):
            validate_sql("TRUNCATE TABLE orders")

    def test_truncate_mixed_case_blocked(self):
        with pytest.raises(ValidationError, match="TRUNCATE"):
            validate_sql("tRuNcAtE TABLE orders")

    # ---- ALTER ----

    def test_alter_blocked(self):
        with pytest.raises(ValidationError, match="ALTER"):
            validate_sql("ALTER TABLE users ADD COLUMN age INT")

    # ---- DELETE / UPDATE without WHERE ----

    def test_delete_without_where_blocked(self):
        with pytest.raises(ValidationError):
            validate_sql("DELETE FROM users")

    def test_delete_with_where_allowed(self):
        """DELETE with WHERE is acceptable — we don't block all DML."""
        # Should not raise
        validate_sql("DELETE FROM sessions WHERE expired_at < :cutoff")

    def test_update_without_where_blocked(self):
        with pytest.raises(ValidationError):
            validate_sql("UPDATE users SET status = 'inactive'")

    def test_update_with_where_allowed(self):
        validate_sql("UPDATE users SET status = :status WHERE id = :id")

    # ---- SELECT * ----

    def test_select_star_blocked(self):
        with pytest.raises(ValidationError, match="SELECT \\*"):
            validate_sql("SELECT * FROM users")

    def test_select_named_columns_allowed(self):
        validate_sql("SELECT id, name, email FROM users WHERE id = :id")

    # ---- Positional params (%s false-positive regression) ----

    def test_percent_s_in_string_literal_allowed(self):
        """
        Regression: old regex-on-full-SQL approach would flag
        WHERE url LIKE '%s%' as containing a positional param.
        """
        validate_sql("SELECT id FROM events WHERE url LIKE '%s%'")

    def test_percent_s_as_actual_param_blocked(self):
        """A bare %s used as a real positional parameter should still fail."""
        with pytest.raises(ValidationError, match="Positional"):
            validate_sql("SELECT id FROM users WHERE id = %s")

    def test_question_mark_blocked(self):
        with pytest.raises(ValidationError, match="Positional"):
            validate_sql("SELECT id FROM users WHERE id = ?")

    def test_dollar_param_blocked(self):
        with pytest.raises(ValidationError, match="Positional"):
            validate_sql("SELECT id FROM users WHERE id = $1")

    def test_named_param_allowed(self):
        validate_sql("SELECT id, name FROM users WHERE id = :user_id")

    # ---- Valid complex query ----

    def test_complex_join_query_allowed(self):
        sql = """
            SELECT u.id, u.name, COUNT(o.id) AS order_count
            FROM users u
            INNER JOIN orders o ON o.user_id = u.id
            WHERE u.created_at > :since
            GROUP BY u.id, u.name
            ORDER BY order_count DESC
        """
        validate_sql(sql)  # Should not raise

    def test_empty_sql_does_not_raise(self):
        """Empty SQL is handled upstream; validator should pass silently."""
        validate_sql("")
        validate_sql("   ")
