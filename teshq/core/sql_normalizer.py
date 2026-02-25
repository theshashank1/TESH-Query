"""
SQL Normalization for TESH-Query v2.

Uses sqlparse to format and normalize SQL for stable, consistent output.
This ensures deterministic formatting for tests and display.
"""

import sqlparse


def normalize_sql(sql: str) -> str:
    """
    Normalize and format a SQL string using sqlparse.

    Applies consistent formatting:
    - Uppercase SQL keywords
    - Normalized whitespace
    - Reindented for readability

    Args:
        sql: Raw SQL string.

    Returns:
        Normalized SQL string.
    """
    if not sql or not sql.strip():
        return ""

    formatted = sqlparse.format(
        sql,
        reindent=True,
        keyword_case="upper",
        strip_whitespace=True,
    )
    return formatted.strip()
