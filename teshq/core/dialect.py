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
    """Supported SQL dialects."""
    SQLITE = "SQLite"
    POSTGRESQL = "PostgreSQL"
    MYSQL = "MySQL"
    MSSQL = "SQL Server (T-SQL)"
    ORACLE = "Oracle"
    GENERIC = "SQL"

    def __str__(self) -> str:
        return self.value


# URL prefix → dialect mapping (order matters: first match wins)
_URL_PREFIX_MAP = (
    ("sqlite", SQLDialect.SQLITE),
    ("postgresql", SQLDialect.POSTGRESQL),
    ("postgres", SQLDialect.POSTGRESQL),
    ("mysql", SQLDialect.MYSQL),
    ("mariadb", SQLDialect.MYSQL),
    ("mssql", SQLDialect.MSSQL),
    ("sqlserver", SQLDialect.MSSQL),
    ("oracle", SQLDialect.ORACLE),
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
    }
    return hints.get(dialect, "")
