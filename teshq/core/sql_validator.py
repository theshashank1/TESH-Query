"""
SQL Validation Layer for TESH-Query v2.

Enforces safety rules before any SQL is executed. Raises ValidationError
for any query that violates the rules. Never executes invalid SQL.
"""

import re

from teshq.utils.validation import ValidationError


# Compiled patterns for efficiency
_DROP_PATTERN = re.compile(r"\bDROP\b", re.IGNORECASE)
_TRUNCATE_PATTERN = re.compile(r"\bTRUNCATE\b", re.IGNORECASE)
_ALTER_PATTERN = re.compile(r"\bALTER\b", re.IGNORECASE)
_DELETE_PATTERN = re.compile(r"\bDELETE\b", re.IGNORECASE)
_UPDATE_PATTERN = re.compile(r"\bUPDATE\b", re.IGNORECASE)
_WHERE_PATTERN = re.compile(r"\bWHERE\b", re.IGNORECASE)
_SELECT_STAR_PATTERN = re.compile(r"\bSELECT\s+\*", re.IGNORECASE)
_NAMED_PARAM_PATTERN = re.compile(r":[a-zA-Z_][a-zA-Z0-9_]*")
_POSITIONAL_PARAM_PATTERN = re.compile(r"\?|\$\d+|%s")


def validate_sql(sql: str) -> None:
    """
    Validate SQL against safety rules.

    Rules enforced:
    - No DROP statements
    - No TRUNCATE statements
    - No ALTER statements
    - No DELETE without WHERE
    - No UPDATE without WHERE
    - No SELECT *
    - Named params must use :param_name syntax (no positional params)

    Args:
        sql: The SQL string to validate.

    Raises:
        ValidationError: If any safety rule is violated.
    """
    if _DROP_PATTERN.search(sql):
        raise ValidationError(
            "DROP statements are not allowed.",
            field="sql",
        )

    if _TRUNCATE_PATTERN.search(sql):
        raise ValidationError(
            "TRUNCATE statements are not allowed.",
            field="sql",
        )

    if _ALTER_PATTERN.search(sql):
        raise ValidationError(
            "ALTER statements are not allowed.",
            field="sql",
        )

    if _DELETE_PATTERN.search(sql) and not _WHERE_PATTERN.search(sql):
        raise ValidationError(
            "DELETE without WHERE clause is not allowed.",
            field="sql",
        )

    if _UPDATE_PATTERN.search(sql) and not _WHERE_PATTERN.search(sql):
        raise ValidationError(
            "UPDATE without WHERE clause is not allowed.",
            field="sql",
        )

    if _SELECT_STAR_PATTERN.search(sql):
        raise ValidationError(
            "SELECT * is not allowed. Specify explicit column names.",
            field="sql",
        )

    if _POSITIONAL_PARAM_PATTERN.search(sql):
        raise ValidationError(
            "Positional parameters (?, $1, %s) are not allowed. Use :param_name syntax.",
            field="sql",
        )
