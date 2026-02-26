"""
Core Pydantic models for TESH-Query v2.

These are the canonical data structures shared between the CLI layer,
the core engine, and the public SDK API. No CLI or database imports
belong here — pure data models only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# LLM / SQL Generation
# ---------------------------------------------------------------------------


class QueryPlan(BaseModel):
    """Stage 1 output: structured plan describing what the SQL query should do."""

    tables: List[str]
    filters: List[str]
    aggregations: List[str]
    joins_needed: List[str]


class SQLQuery(BaseModel):
    """Structured output from the LLM SQL generator."""

    query: str = Field(..., description="The SQL statement with :named_params placeholders")
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Named parameter values matching placeholders in `query`",
    )

    def is_read_only(self) -> bool:
        """Return True if the query is a single SELECT statement (prevents multi-statement bypass)."""
        statements = []
        current = []
        in_single_quote = False
        in_double_quote = False
        
        for char in self.query:
            if char == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
            elif char == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
                
            if char == ';' and not in_single_quote and not in_double_quote:
                stmt_str = "".join(current).strip()
                if stmt_str:
                    statements.append(stmt_str)
                current = []
            else:
                current.append(char)
                
        # Catch the last statement if it doesn't end with a semicolon
        last_stmt = "".join(current).strip()
        if last_stmt:
            statements.append(last_stmt)
            
        return len(statements) == 1 and statements[0].upper().startswith("SELECT")


# ---------------------------------------------------------------------------
# Schema Introspection
# ---------------------------------------------------------------------------


class ColumnInfo(BaseModel):
    """Metadata about a single database column."""

    name: str
    type: str
    nullable: bool = True
    primary_key: bool = False
    foreign_key: Optional[str] = Field(
        None,
        description="Referenced table.column, e.g. 'users.id'",
    )
    default: Optional[str] = None


class TableInfo(BaseModel):
    """Metadata about a single database table."""

    name: str
    columns: List[ColumnInfo] = Field(default_factory=list)
    row_count_estimate: Optional[int] = None

    def compressed_repr(self) -> str:
        """
        Return a compact, token-efficient schema line for LLM consumption.

        Example: "TABLE users (id INT PK, name TEXT NN, email TEXT NN)"
        """
        col_parts = []
        for col in self.columns:
            flags = []
            if col.primary_key:
                flags.append("PK")
            if not col.nullable:
                flags.append("NN")
            if col.foreign_key:
                flags.append(f"FK→{col.foreign_key}")
            suffix = " " + " ".join(flags) if flags else ""
            col_parts.append(f"{col.name} {col.type}{suffix}")
        return f"TABLE {self.name} ({', '.join(col_parts)})"


class SchemaInfo(BaseModel):
    """Full database schema snapshot."""

    tables: Dict[str, TableInfo] = Field(default_factory=dict)
    dialect: str = "unknown"
    database_name: Optional[str] = None

    def to_compressed_text(self) -> str:
        """
        Convert schema to a compact text representation for LLM prompts.

        Reduces token usage by 60–80% vs raw JSON schema.
        """
        lines = []
        if self.database_name:
            lines.append(f"# Database: {self.database_name} ({self.dialect})")
        for table in self.tables.values():
            lines.append(table.compressed_repr())
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Query Execution
# ---------------------------------------------------------------------------


class QueryResult(BaseModel):
    """The full result of a TESH-Query execution."""

    sql: str = Field(..., description="The SQL that was actually executed")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    columns: List[str] = Field(default_factory=list)
    execution_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def cost_estimate_usd(self) -> float:
        """Rough cost estimate using gemini-2.0-flash-lite pricing."""
        INPUT_COST_PER_1K = 0.000075
        OUTPUT_COST_PER_1K = 0.0003
        return (self.prompt_tokens / 1000 * INPUT_COST_PER_1K) + (
            self.completion_tokens / 1000 * OUTPUT_COST_PER_1K
        )

    def is_empty(self) -> bool:
        return self.row_count == 0
