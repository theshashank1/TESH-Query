"""
SQL Validation Layer for TESH-Query v2.

Enforces safety rules before any SQL is executed. Raises ValidationError
for any query that violates the rules. Never executes invalid SQL.

Uses sqlparse AST-based parsing for DDL/DML detection to avoid regex
bypass via clever casing, embedded comments, or whitespace tricks.
SELECT * and positional-param checks use targeted regex, but only after
string literals are stripped so false positives (e.g. WHERE url LIKE '%s%')
are not triggered.
"""

import re
from typing import List

import sqlparse
from sqlparse.sql import Statement

from teshq.core.validation import ValidationError


# Destructive statement types that must never be executed.
# sqlparse returns these as the stmt.get_type() value.
_BLOCKED_STATEMENT_TYPES = frozenset(
    {
        "DROP",
        "TRUNCATE",
        "ALTER",
        "CREATE",
    }
)

# DDL/DML keyword tokens we block via AST token inspection when
# get_type() returns None or "UNKNOWN" (e.g. multi-keyword statements).
_BLOCKED_KEYWORDS = frozenset(
    {
        "DROP",
        "TRUNCATE",
        "ALTER",
        "CREATE",
        "REPLACE",
    }
)

# Regex for SELECT * check — applied on the full SQL (still safe because
# we only check for a structural pattern, not user-supplied literals).
_SELECT_STAR_PATTERN = re.compile(r"\bSELECT\s+\*", re.IGNORECASE)

# Named-param pattern (used to verify correct param style)
_NAMED_PARAM_PATTERN = re.compile(r":[a-zA-Z_][a-zA-Z0-9_]*")

# Positional-param pattern — applied ONLY on the SQL *after* string literals
# have been stripped to avoid false positives like WHERE url LIKE '%s%'.
_POSITIONAL_PARAM_PATTERN = re.compile(r"\?|\$\d+|%s")

# Regex that strips single-quoted string literals (handles '' escaping)
_STRING_LITERAL_RE = re.compile(r"'(?:''|[^'])*'")


def _strip_string_literals(sql: str) -> str:
    """Remove all single-quoted string literals from *sql*."""
    return _STRING_LITERAL_RE.sub("''", sql)


def _get_first_keyword(stmt: Statement) -> str:
    """Return the normalized first keyword in a statement."""
    from sqlparse import tokens as T

    for token in stmt.flatten():
        if token.ttype in (T.Keyword.DML, T.Keyword.DDL):
            return token.normalized.upper()
        # Some multi-word DDL (e.g. CREATE OR REPLACE) starts with Keyword
        if token.ttype is T.Keyword and token.normalized.upper() in _BLOCKED_KEYWORDS:
            return token.normalized.upper()
    return ""


def _requires_where(stmt: Statement) -> bool:
    """Return True if the statement is DELETE or UPDATE."""
    kw = _get_first_keyword(stmt)
    return kw in ("DELETE", "UPDATE")


def _has_where_clause(stmt: Statement) -> bool:
    """Return True if the statement contains a WHERE keyword."""
    from sqlparse import tokens as T

    for token in stmt.flatten():
        if token.ttype is T.Keyword and token.normalized.upper() == "WHERE":
            return True
    return False


def validate_sql(sql: str) -> None:
    """
    Validate SQL against safety rules using sqlparse AST analysis.

    Rules enforced:
    - No DROP / TRUNCATE / ALTER / CREATE statements
    - No DELETE without WHERE clause
    - No UPDATE without WHERE clause
    - No SELECT *
    - No positional parameters (?, $1, %s) — must use :param_name syntax

    Args:
        sql: The SQL string to validate.

    Raises:
        ValidationError: If any safety rule is violated.
    """
    if not sql or not sql.strip():
        return  # Empty SQL is handled upstream as a generation failure

    # Parse all statements (handles multi-statement input)
    parsed: List[Statement] = sqlparse.parse(sql)

    for stmt in parsed:
        stmt_type: str = (stmt.get_type() or "").upper()

        # 1. Block DDL by statement type
        if stmt_type in _BLOCKED_STATEMENT_TYPES:
            raise ValidationError(
                f"{stmt_type} statements are not allowed.",
                field="sql",
            )

        # 2. Block DDL by first keyword (catches cases where get_type()
        #    returns None, e.g. "CREATE OR REPLACE PROCEDURE ...")
        first_kw = _get_first_keyword(stmt)
        if first_kw in _BLOCKED_KEYWORDS:
            raise ValidationError(
                f"{first_kw} statements are not allowed.",
                field="sql",
            )

        # 3. DELETE / UPDATE must have WHERE
        if _requires_where(stmt) and not _has_where_clause(stmt):
            raise ValidationError(
                f"{first_kw} without WHERE clause is not allowed.",
                field="sql",
            )

    # 4. SELECT * check (regex on full SQL — structural pattern, safe)
    if _SELECT_STAR_PATTERN.search(sql):
        raise ValidationError(
            "SELECT * is not allowed. Specify explicit column names.",
            field="sql",
        )

    # 5. Positional parameters — check on SQL with string literals stripped
    #    to avoid false positives like WHERE url LIKE '%s%'
    stripped = _strip_string_literals(sql)
    if _POSITIONAL_PARAM_PATTERN.search(stripped):
        raise ValidationError(
            "Positional parameters (?, $1, %s) are not allowed. Use :param_name syntax.",
            field="sql",
        )
