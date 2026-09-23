"""
Centralized SQL Dialect Detection and Rules for TESH-Query.

Provides a single source of truth for:
- Detecting the SQL dialect from a database URL
- Dialect-specific SQL generation rules for LLM prompts
- Dialect-specific function reference hints for local models

Usage::

    from teshq.core.dialect import detect_dialect, get_dialect_rules, get_dialect_hints

    dialect = detect_dialect("sqlite:///my.db")       # → "SQLite"
    rules = get_dialect_rules(dialect)                 # → dialect-specific generation rules
    hints = get_dialect_hints(dialect)                 # → function reference for local models
"""

from __future__ import annotations

from enum import Enum
from typing import Optional


class SQLDialect(str, Enum):
    """Supported SQL dialects.

    Ordered by analyst relevance:
      Tier 1 – Cloud Data Warehouses & Lakehouses
      Tier 2 – Local & Real-time OLAP Engines
      Tier 3 – Operational RDBMS (replicas / read-only mirrors)
      Tier 4 – Local development & generic fallback
    """
    # ── Tier 1: Cloud Data Warehouses & Lakehouses ────────────────────────
    BIGQUERY = "BigQuery"
    SNOWFLAKE = "Snowflake"
    DATABRICKS = "Databricks SQL"
    REDSHIFT = "Amazon Redshift"
    # ── Tier 2: Local & Real-time OLAP ────────────────────────────────────
    DUCKDB = "DuckDB"
    CLICKHOUSE = "ClickHouse"
    # ── Tier 3: Operational RDBMS ─────────────────────────────────────────
    POSTGRESQL = "PostgreSQL"
    MYSQL = "MySQL"
    MSSQL = "SQL Server (T-SQL)"
    ORACLE = "Oracle"
    # ── Tier 4: Local development & generic ───────────────────────────────
    SQLITE = "SQLite"
    GENERIC = "SQL"

    def __str__(self) -> str:
        return self.value


# URL prefix → dialect mapping (order matters: first match wins).
# Longer / more-specific prefixes come first so that e.g.
# ``redshift+psycopg2://`` matches REDSHIFT before POSTGRESQL.
_URL_PREFIX_MAP = (
    # ── Cloud Data Warehouses & Lakehouses ────────────────────────────────
    ("bigquery", SQLDialect.BIGQUERY),
    ("snowflake", SQLDialect.SNOWFLAKE),
    ("databricks", SQLDialect.DATABRICKS),
    ("redshift", SQLDialect.REDSHIFT),      # redshift+psycopg2://
    # ── Local & Real-time OLAP ────────────────────────────────────────────
    ("duckdb", SQLDialect.DUCKDB),
    ("clickhouse", SQLDialect.CLICKHOUSE),
    # ── Operational RDBMS ─────────────────────────────────────────────────
    ("postgresql", SQLDialect.POSTGRESQL),
    ("postgres", SQLDialect.POSTGRESQL),
    ("mysql", SQLDialect.MYSQL),
    ("mariadb", SQLDialect.MYSQL),
    ("mssql", SQLDialect.MSSQL),
    ("sqlserver", SQLDialect.MSSQL),
    ("oracle", SQLDialect.ORACLE),
    # ── Local development ─────────────────────────────────────────────────
    ("sqlite", SQLDialect.SQLITE),
)


def detect_dialect(db_url: Optional[str] = None) -> SQLDialect:
    """
    Detect SQL dialect from a database URL.

    Falls back to reading the configured DATABASE_URL if none is provided.
    Returns ``SQLDialect.GENERIC`` when the dialect cannot be determined.

    Args:
        db_url: Database connection URL (e.g. ``sqlite:///my.db``).

    Returns:
        The detected :class:`SQLDialect`.
    """
    if not db_url:
        try:
            from teshq.config.loader import get_database_url
            db_url = get_database_url()
        except Exception:
            pass

    if not db_url:
        return SQLDialect.GENERIC

    url_lower = db_url.lower().strip()
    for prefix, dialect in _URL_PREFIX_MAP:
        if url_lower.startswith(prefix):
            return dialect

    return SQLDialect.GENERIC


def get_dialect_display_name(dialect: SQLDialect, db_url: Optional[str] = None) -> str:
    """Return a human-readable dialect name suitable for LLM prompts.

    For known dialects (SQLite, PostgreSQL, etc.) returns the enum value.
    For ``GENERIC``, returns the URL scheme name if available (e.g. ``"Bigquery SQL"``),
    otherwise falls back to ``"SQL"``.

    Args:
        dialect: The detected SQL dialect enum.
        db_url: Optional database URL (used to extract scheme for GENERIC dialects).

    Returns:
        A display name string like ``"SQLite"``, ``"PostgreSQL"``, or ``"Bigquery SQL"``.
    """
    if dialect != SQLDialect.GENERIC:
        return str(dialect)

    # Try to extract from a provided db_url
    if db_url and "://" in db_url:
        scheme = db_url.lower().split("://")[0].split("+")[0]
        return f"{scheme.title()} SQL"

    return str(dialect)


def get_dialect_rules(dialect: SQLDialect) -> str:
    """
    Return dialect-specific SQL generation rules for LLM system prompts.

    These rules prevent the most common cross-dialect syntax errors
    (e.g. ``FETCH FIRST`` on SQLite, ``LIMIT`` on Oracle, etc.).

    Args:
        dialect: The target SQL dialect.

    Returns:
        A multi-line string of rules, or ``""`` for generic/unknown dialects.
    """
    rules = {
        # ── Tier 1: Cloud Data Warehouses & Lakehouses ────────────────────
        SQLDialect.BIGQUERY: (
            "\nGoogle BigQuery-specific rules (MUST follow):\n"
            "- Use backticks for identifiers: `project.dataset.table` or `dataset.table`.\n"
            "- NEVER use double-quotes for identifiers.\n"
            "- Use LIMIT N for row limiting.\n"
            "- Date difference: DATE_DIFF(end_date, start_date, DAY). NEVER use DATEDIFF.\n"
            "- Date arithmetic: DATE_SUB(date, INTERVAL n DAY), DATE_ADD(date, INTERVAL n MONTH).\n"
            "- Date truncation: DATE_TRUNC(date_col, MONTH).\n"
            "- Current date/time: CURRENT_DATE(), CURRENT_TIMESTAMP().\n"
            "- Date parts: EXTRACT(YEAR FROM date_col). No YEAR(), MONTH(), DAY() functions.\n"
            "- String concat: CONCAT(col1, col2). || is NOT supported.\n"
            "- Safe casting: SAFE_CAST(val AS TYPE) to avoid runtime errors.\n"
            "- Use REGEXP_CONTAINS(col, r'pattern') for regex matching. No REGEXP or RLIKE.\n"
            "- Null replacement: IFNULL(x, y) or COALESCE(x, y).\n"
            "- When temporal filtering is implied, include a WHERE clause on the partition\n"
            "  date column to reduce cost and improve performance.\n"
        ),
        SQLDialect.SNOWFLAKE: (
            "\nSnowflake-specific rules (MUST follow):\n"
            "- Identifiers are case-insensitive by default. Use double-quotes only when\n"
            "  preserving mixed-case or special characters.\n"
            "- Use LIMIT N for row limiting.\n"
            "- Date difference: DATEDIFF('day', start_date, end_date). Note part as STRING.\n"
            "- Date arithmetic: DATEADD('day', n, date). Note part as STRING.\n"
            "- Date truncation: DATE_TRUNC('month', date_col).\n"
            "- Current date/time: CURRENT_DATE(), CURRENT_TIMESTAMP().\n"
            "- Date parts: EXTRACT(YEAR FROM date_col) or DATE_PART('year', date_col).\n"
            "- String concat: col1 || col2 or CONCAT(col1, col2).\n"
            "- Use ILIKE for case-insensitive string matching.\n"
            "- Semi-structured data: use colon notation for VARIANT/JSON columns\n"
            "  e.g. payload:user_id::string.\n"
            "- Null replacement: NVL(x, y), IFNULL(x, y), or COALESCE(x, y).\n"
        ),
        SQLDialect.DATABRICKS: (
            "\nDatabricks SQL-specific rules (MUST follow):\n"
            "- Use backticks for identifiers with special chars or reserved words.\n"
            "- Use LIMIT N for row limiting.\n"
            "- Date difference: DATEDIFF(end_date, start_date) returns days.\n"
            "- Date arithmetic: DATE_ADD(date, n) adds days, DATE_SUB(date, n) subtracts days.\n"
            "- Date truncation: DATE_TRUNC('MONTH', date_col) or TRUNC(date_col, 'MM').\n"
            "- Current date/time: CURRENT_DATE(), CURRENT_TIMESTAMP().\n"
            "- Date parts: YEAR(date_col), MONTH(date_col), DAY(date_col).\n"
            "- String concat: CONCAT(col1, col2) or col1 || col2.\n"
            "- Null replacement: COALESCE(x, y) or NVL(x, y).\n"
            "- Use Delta Lake table references: catalog.schema.table.\n"
        ),
        SQLDialect.REDSHIFT: (
            "\nAmazon Redshift-specific rules (MUST follow):\n"
            "- Use LIMIT N for row limiting.\n"
            "- Date difference: DATEDIFF(day, start_date, end_date). Note part without quotes.\n"
            "- Date arithmetic: DATEADD(day, n, date). Note part without quotes.\n"
            "- Date truncation: DATE_TRUNC('month', date_col).\n"
            "- Current date/time: CURRENT_DATE, GETDATE(), SYSDATE.\n"
            "- Date parts: EXTRACT(YEAR FROM date_col) or DATE_PART('year', date_col).\n"
            "- String concat: col1 || col2 or CONCAT(col1, col2).\n"
            "- Use ILIKE for case-insensitive string matching.\n"
            "- Null replacement: NVL(x, y) or COALESCE(x, y).\n"
            "- Redshift does NOT support RIGHT / FULL OUTER JOIN on all distributions.\n"
        ),
        # ── Tier 2: Local & Real-time OLAP ────────────────────────────────
        SQLDialect.DUCKDB: (
            "\nDuckDB-specific rules (MUST follow):\n"
            "- Use LIMIT N for row limiting.\n"
            "- Date difference: date_diff('day', start_date, end_date).\n"
            "- Date arithmetic: date - INTERVAL 7 DAY, date + INTERVAL 1 MONTH.\n"
            "- Date truncation: date_trunc('month', date_col).\n"
            "- Current date/time: current_date, current_timestamp (no parentheses).\n"
            "- Date parts: EXTRACT(YEAR FROM date_col) or year(date_col).\n"
            "- String concat: col1 || col2 or CONCAT(col1, col2).\n"
            "- Use ILIKE for case-insensitive string matching.\n"
            "- DuckDB supports GROUP BY ALL to auto-group all non-aggregate SELECT cols.\n"
            "- DuckDB supports SELECT * EXCLUDE (col1, col2) to drop specific cols.\n"
            "- DuckDB can directly query Parquet/CSV files: SELECT * FROM 'file.parquet'.\n"
            "- Null replacement: IFNULL(x, y) or COALESCE(x, y).\n"
        ),
        SQLDialect.CLICKHOUSE: (
            "\nClickHouse-specific rules (MUST follow):\n"
            "- Use LIMIT N for row limiting.\n"
            "- Date difference: dateDiff('day', start_date, end_date). Note camelCase.\n"
            "- Date arithmetic: date + INTERVAL 7 DAY, date - INTERVAL 1 MONTH.\n"
            "- Date truncation: toStartOfMonth(date_col), toStartOfYear(date_col).\n"
            "- Current date/time: today(), now().\n"
            "- Date parts: toYear(date_col), toMonth(date_col), toDayOfMonth(date_col).\n"
            "- Convert to date: toDate(col), toDateTime(col).\n"
            "- Formatted dates: formatDateTime(date_col, '%Y-%m-%d').\n"
            "- String concat: concat(col1, col2). || is NOT supported.\n"
            "- Use LIKE or match(col, 'pattern') for string matching.\n"
            "- ClickHouse uses MergeTree family engines. Prefer filtering on ORDER BY\n"
            "  key columns for performance.\n"
            "- Null replacement: ifNull(x, y) or COALESCE(x, y).\n"
        ),
        # ── Tier 3: Operational RDBMS ─────────────────────────────────────
        SQLDialect.POSTGRESQL: (
            "\nPostgreSQL-specific rules (MUST follow):\n"
            "- Use LIMIT N or FETCH FIRST N ROWS ONLY for row limiting.\n"
            "- Use (date2 - date1) for date intervals, DATE_PART('day', date2 - date1) for days.\n"
            "- Use CURRENT_DATE for current date.\n"
            "- Use col1 || col2 or CONCAT(col1, col2) for string concatenation.\n"
            "- Use ILIKE for case-insensitive string matching.\n"
        ),
        SQLDialect.MYSQL: (
            "\nMySQL-specific rules (MUST follow):\n"
            "- Use LIMIT N for row limiting. NEVER use FETCH FIRST N ROWS ONLY.\n"
            "- Use DATEDIFF(date2, date1) for date difference in days.\n"
            "- Use CURDATE() or CURRENT_DATE for current date.\n"
            "- Use YEAR(date_col), MONTH(date_col), DAY(date_col) for date parts.\n"
            "- Use CONCAT(col1, col2) for string concatenation.\n"
        ),
        SQLDialect.MSSQL: (
            "\nSQL Server (T-SQL)-specific rules (MUST follow):\n"
            "- Use TOP N instead of LIMIT N.\n"
            "- Use DATEDIFF(day, date1, date2) for date difference.\n"
            "- Use GETDATE() for current date/time.\n"
            "- Use + operator for string concatenation.\n"
            "- Use ISNULL(x, y) instead of IFNULL or COALESCE for two args.\n"
        ),
        SQLDialect.ORACLE: (
            "\nOracle-specific rules (MUST follow):\n"
            "- Use FETCH FIRST N ROWS ONLY (12c+) or ROWNUM <= N for row limiting.\n"
            "- Use SYSDATE for current date.\n"
            "- Use col1 || col2 for string concatenation.\n"
            "- Use NVL(x, y) instead of IFNULL or ISNULL.\n"
        ),
        # ── Tier 4: Local development ─────────────────────────────────────
        SQLDialect.SQLITE: (
            "\nSQLite-specific rules (MUST follow):\n"
            "- Use LIMIT N for row limiting. NEVER use FETCH FIRST N ROWS ONLY.\n"
            "- Use CAST(julianday(date2) - julianday(date1) AS INTEGER) for date difference in days.\n"
            "- Use DATE('now') for current date.\n"
            "- Use strftime('%Y', date_col) for date parts. No YEAR(), MONTH(), DAY() functions.\n"
            "- Use col1 || col2 for string concatenation. No CONCAT() function.\n"
            "- Use IFNULL(x, y) instead of ISNULL.\n"
            "- No DATEDIFF, DATEADD functions.\n"
            "- Boolean values: use 1 and 0, not TRUE/FALSE.\n"
        ),
    }
    return rules.get(dialect, "")


def get_dialect_hints(dialect: SQLDialect) -> str:
    """
    Return dialect-specific function reference hints for local model prompts.

    These are more concise than ``get_dialect_rules`` and formatted as a
    quick-reference cheat sheet for smaller models with limited context.

    Args:
        dialect: The target SQL dialect.

    Returns:
        A multi-line function reference string, or ``""`` for unknown dialects.
    """
    hints = {
        # ── Tier 1: Cloud Data Warehouses & Lakehouses ────────────────────
        SQLDialect.BIGQUERY: (
            "BigQuery function reference:\n"
            "- Identifiers: backticks `dataset.table` (NEVER double-quotes)\n"
            "- Date diff days: DATE_DIFF(end, start, DAY)\n"
            "- Date add/sub: DATE_ADD(d, INTERVAL n DAY), DATE_SUB(d, INTERVAL n DAY)\n"
            "- Date trunc: DATE_TRUNC(d, MONTH)\n"
            "- Current: CURRENT_DATE(), CURRENT_TIMESTAMP()\n"
            "- Parts: EXTRACT(YEAR FROM d)\n"
            "- Concat: CONCAT(a, b) (no || operator)\n"
            "- Safe cast: SAFE_CAST(v AS TYPE)\n"
            "- Row limit: LIMIT N\n"
        ),
        SQLDialect.SNOWFLAKE: (
            "Snowflake function reference:\n"
            "- Date diff: DATEDIFF('day', start, end)\n"
            "- Date add: DATEADD('day', n, d)\n"
            "- Date trunc: DATE_TRUNC('month', d)\n"
            "- Current: CURRENT_DATE(), CURRENT_TIMESTAMP()\n"
            "- Concat: a || b or CONCAT(a, b)\n"
            "- Case-insensitive match: ILIKE\n"
            "- JSON access: col:key::string\n"
            "- Row limit: LIMIT N\n"
        ),
        SQLDialect.DATABRICKS: (
            "Databricks SQL function reference:\n"
            "- Date diff days: DATEDIFF(end, start)\n"
            "- Date add: DATE_ADD(d, n) / DATE_SUB(d, n)\n"
            "- Date trunc: DATE_TRUNC('MONTH', d)\n"
            "- Parts: YEAR(d), MONTH(d), DAY(d)\n"
            "- Current: CURRENT_DATE(), CURRENT_TIMESTAMP()\n"
            "- Concat: CONCAT(a, b) or a || b\n"
            "- Row limit: LIMIT N\n"
        ),
        SQLDialect.REDSHIFT: (
            "Redshift function reference:\n"
            "- Date diff: DATEDIFF(day, start, end)\n"
            "- Date add: DATEADD(day, n, d)\n"
            "- Date trunc: DATE_TRUNC('month', d)\n"
            "- Current: CURRENT_DATE, GETDATE(), SYSDATE\n"
            "- Concat: a || b or CONCAT(a, b)\n"
            "- Case-insensitive match: ILIKE\n"
            "- Row limit: LIMIT N\n"
        ),
        # ── Tier 2: Local & Real-time OLAP ────────────────────────────────
        SQLDialect.DUCKDB: (
            "DuckDB function reference:\n"
            "- Date diff: date_diff('day', start, end)\n"
            "- Date arithmetic: d - INTERVAL 7 DAY\n"
            "- Date trunc: date_trunc('month', d)\n"
            "- Current: current_date, current_timestamp (no parens)\n"
            "- Parts: EXTRACT(YEAR FROM d) or year(d)\n"
            "- Concat: a || b or CONCAT(a, b)\n"
            "- GROUP BY ALL, SELECT * EXCLUDE (col)\n"
            "- Query files: SELECT * FROM 'file.parquet'\n"
            "- Row limit: LIMIT N\n"
        ),
        SQLDialect.CLICKHOUSE: (
            "ClickHouse function reference:\n"
            "- Date diff: dateDiff('day', start, end)\n"
            "- Date trunc: toStartOfMonth(d), toStartOfYear(d)\n"
            "- Current: today(), now()\n"
            "- Parts: toYear(d), toMonth(d), toDayOfMonth(d)\n"
            "- Convert: toDate(col), toDateTime(col)\n"
            "- Concat: concat(a, b) (no || operator)\n"
            "- Null: ifNull(x, y)\n"
            "- Row limit: LIMIT N\n"
        ),
        # ── Tier 3: Operational RDBMS ─────────────────────────────────────
        SQLDialect.POSTGRESQL: (
            "PostgreSQL function reference:\n"
            "- Date difference: (date2 - date1) returns interval, or DATE_PART('day', date2 - date1)\n"
            "- Current date: CURRENT_DATE\n"
            "- String concat: col1 || col2 or CONCAT(col1, col2)\n"
        ),
        SQLDialect.MYSQL: (
            "MySQL function reference:\n"
            "- Date difference in days: DATEDIFF(date2, date1)\n"
            "- Current date: CURDATE() or CURRENT_DATE\n"
            "- Date parts: YEAR(date_col), MONTH(date_col), DAY(date_col)\n"
        ),
        SQLDialect.MSSQL: (
            "SQL Server (T-SQL) function reference:\n"
            "- Date difference in days: DATEDIFF(day, date1, date2)\n"
            "- Current date/time: GETDATE()\n"
            "- Row limiting: SELECT TOP N ... (NEVER use LIMIT)\n"
            "- String concat: col1 + col2\n"
            "- ISNULL(x, y) for null replacement\n"
        ),
        SQLDialect.ORACLE: (
            "Oracle function reference:\n"
            "- Date difference in days: (date2 - date1)\n"
            "- Current date: SYSDATE\n"
            "- Row limiting: FETCH FIRST N ROWS ONLY or WHERE ROWNUM <= N (NEVER use LIMIT)\n"
            "- String concat: col1 || col2\n"
            "- NVL(x, y) for null replacement\n"
        ),
        # ── Tier 4: Local development ─────────────────────────────────────
        SQLDialect.SQLITE: (
            "SQLite function reference:\n"
            "- Date difference in days: CAST(julianday(date2) - julianday(date1) AS INTEGER)\n"
            "- Current date: DATE('now')\n"
            "- Date parts: strftime('%Y', date_col), strftime('%m', date_col)\n"
            "- String concat: col1 || col2 (no CONCAT function)\n"
            "- IFNULL(x, y) instead of COALESCE for two args\n"
            "- No DATEDIFF, DATEADD, YEAR(), MONTH(), DAY() functions\n"
            "- Row limit: LIMIT N (NEVER use FETCH FIRST)\n"
            "- List tables: SELECT name FROM sqlite_master WHERE type='table'\n"
        ),
    }
    return hints.get(dialect, "")
