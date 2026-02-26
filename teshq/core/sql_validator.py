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
# We still need statement splitting, but comments are stripped carefully
def _split_statements(sql: str) -> list:
    """Safely strip comments and split SQL into statements, respecting quotes."""
    statements = []
    current_stmt = []
    
    in_sq = False  # Single quote
    in_dq = False  # Double quote
    in_line_comment = False
    in_block_comment = False
    
    i = 0
    n = len(sql)
    
    while i < n:
        char = sql[i]
        
        # Handle state transitions
        if in_line_comment:
            if char == '\n':
                in_line_comment = False
                current_stmt.append(' ')
            i += 1
            continue
            
        if in_block_comment:
            if char == '*' and i + 1 < n and sql[i+1] == '/':
                in_block_comment = False
                current_stmt.append(' ')
                i += 2
            else:
                i += 1
            continue
            
        # String literals
        if char == "'" and not in_dq:
            in_sq = not in_sq
        elif char == '"' and not in_sq:
            in_dq = not in_dq
            
        # Comments (only if outside string literals)
        if not in_sq and not in_dq:
            if char == '-' and i + 1 < n and sql[i+1] == '-':
                in_line_comment = True
                i += 2
                continue
            if char == '/' and i + 1 < n and sql[i+1] == '*':
                in_block_comment = True
                i += 2
                continue
            
            # Semicolon delimiter
            if char == ';':
                stmt_str = "".join(current_stmt).strip()
                if stmt_str:
                    statements.append(stmt_str)
                current_stmt = []
                i += 1
                continue
                
        # Normal character appends
        current_stmt.append(char)
        i += 1
        
    last_stmt = "".join(current_stmt).strip()
    if last_stmt:
        statements.append(last_stmt)
        
    return statements


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

    # Per-statement WHERE check to prevent multi-statement bypass
    for stmt in _split_statements(sql):
        if _DELETE_PATTERN.search(stmt) and not _WHERE_PATTERN.search(stmt):
            raise ValidationError(
                "DELETE without WHERE clause is not allowed.",
                field="sql",
            )
        if _UPDATE_PATTERN.search(stmt) and not _WHERE_PATTERN.search(stmt):
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
