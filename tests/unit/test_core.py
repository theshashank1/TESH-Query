"""
Unit tests for core token counting, SQL normalization, and query safety inspection.
"""

from teshq.core.models import SQLQuery
from teshq.core.sql_normalizer import normalize_sql
from teshq.core.token_counter import DEFAULT_TOKEN_THRESHOLD, estimate_tokens, exceeds_threshold


class TestTokenCounter:
    """Tests for token estimation heuristics."""

    def test_estimate_tokens_empty(self):
        assert estimate_tokens("") == 1

    def test_estimate_tokens_short(self):
        # 16 chars with 4 chars per token should be around 4 tokens
        assert estimate_tokens("1234567890123456") == 4

    def test_exceeds_threshold(self):
        assert exceeds_threshold("short text", threshold=100) is False
        large_text = "a" * (DEFAULT_TOKEN_THRESHOLD * 5)
        assert exceeds_threshold(large_text, threshold=DEFAULT_TOKEN_THRESHOLD) is True


class TestSqlNormalizer:
    """Tests for SQL normalization and formatting."""

    def test_normalize_empty_sql(self):
        assert normalize_sql("") == ""
        assert normalize_sql("   ") == ""

    def test_normalize_keywords_upper(self):
        sql = "select id, name from users where id = 1"
        normalized = normalize_sql(sql)
        assert "SELECT" in normalized
        assert "FROM" in normalized
        assert "WHERE" in normalized

    def test_normalize_strips_extraneous_whitespace(self):
        sql = "  SELECT   a,   b   FROM   t  "
        normalized = normalize_sql(sql)
        assert normalized.startswith("SELECT")
        assert normalized.endswith("FROM t")


class TestSQLQuerySafety:
    """Tests for SQLQuery read-only validation."""

    def test_single_select_is_read_only(self):
        q = SQLQuery(query="SELECT id, name FROM users", parameters={})
        assert q.is_read_only() is True

    def test_select_with_semicolon_is_read_only(self):
        q = SQLQuery(query="SELECT id, name FROM users;", parameters={})
        assert q.is_read_only() is True

    def test_multi_statement_blocked(self):
        q = SQLQuery(query="SELECT 1; DROP TABLE users;", parameters={})
        assert q.is_read_only() is False

    def test_insert_not_read_only(self):
        q = SQLQuery(query="INSERT INTO users (id) VALUES (1)", parameters={})
        assert q.is_read_only() is False

    def test_update_not_read_only(self):
        q = SQLQuery(query="UPDATE users SET active = 1 WHERE id = 1", parameters={})
        assert q.is_read_only() is False

    def test_quoted_semicolons_allowed_in_single_query(self):
        q = SQLQuery(query="SELECT id FROM users WHERE note = 'semi;colon'", parameters={})
        assert q.is_read_only() is True


class TestIntrospectSecurity:
    """Tests for PII and credential protection during schema introspection."""

    def test_sample_data_masks_sensitive_columns(self, tmp_path):
        import sqlite3
        from teshq.core.introspect import introspect_db

        db_file = tmp_path / "sensitive.sqlite"
        with sqlite3.connect(db_file) as conn:
            conn.execute("""
                CREATE TABLE user_accounts (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    password_hash TEXT,
                    api_secret TEXT,
                    credit_card_num TEXT,
                    public_bio TEXT
                )
            """)
            conn.execute("""
                INSERT INTO user_accounts VALUES (
                    1, 'alice', 'argon2$very_secret_hash', 'sk_live_123456789', '4111222233334444', 'Hello world!'
                )
            """)

        schema = introspect_db(
            db_url=f"sqlite:///{db_file}",
            include_sample_data=True,
            sample_size=1,
        )

        table_info = schema["tables"]["user_accounts"]
        assert "sample_data" in table_info
        samples = table_info["sample_data"]
        assert len(samples) == 1
        sample_row = samples[0]

        # Public fields are preserved
        assert sample_row["username"] == "alice"
        assert sample_row["public_bio"] == "Hello world!"

        # Sensitive credentials MUST be masked
        assert sample_row["password_hash"] == "********"
        assert sample_row["api_secret"] == "********"
        assert sample_row["credit_card_num"] == "********"
        assert "argon2$very_secret_hash" not in str(schema)
        assert "sk_live_123456789" not in str(schema)
        assert "4111222233334444" not in str(schema)

    def test_introspect_includes_database_views(self, tmp_path):
        import sqlite3
        from teshq.core.introspect import introspect_db

        db_file = tmp_path / "views_test.sqlite"
        with sqlite3.connect(db_file) as conn:
            conn.execute("CREATE TABLE products (id INT PRIMARY KEY, name TEXT, price REAL);")
            conn.execute("INSERT INTO products VALUES (1, 'Widget', 19.99);")
            conn.execute("CREATE VIEW expensive_products AS SELECT id, name, price FROM products WHERE price > 10;")
            conn.commit()

        schema = introspect_db(db_url=f"sqlite:///{db_file}")
        assert "products" in schema["tables"]
        assert "expensive_products" in schema["tables"]
        view_cols = [c["name"] for c in schema["tables"]["expensive_products"]["columns"]]
        assert "id" in view_cols
        assert "name" in view_cols
        assert "price" in view_cols

    def test_dialect_detection_for_all_dialects(self):
        from teshq.core.dialect import SQLDialect, detect_dialect, get_dialect_display_name

        cases = [
            ("oracle+cx_oracle://user:pass@host:1521/XEPDB1", SQLDialect.ORACLE, "Oracle"),
            ("cockroachdb://root@host:26257/defaultdb", SQLDialect.POSTGRESQL, "PostgreSQL"),
            ("mariadb://user:pass@host:3306/db", SQLDialect.MYSQL, "MySQL"),
            ("duckdb:///my.duckdb", SQLDialect.DUCKDB, "DuckDB"),
            ("trino://user@host:8080/hive/default", SQLDialect.GENERIC, "Trino SQL"),
            ("teradatasql://user:pass@host/db", SQLDialect.GENERIC, "Teradatasql SQL"),
            ("sap+hana://user:pass@host:30015/db", SQLDialect.GENERIC, "Sap SQL"),
        ]
        for url, expected_dialect, expected_display in cases:
            dialect = detect_dialect(url)
            assert dialect == expected_dialect, f"For {url}, expected {expected_dialect}, got {dialect}"
            display = get_dialect_display_name(dialect, url)
            assert display == expected_display, f"For {url}, expected {expected_display}, got {display}"
