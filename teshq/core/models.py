"""
Core Pydantic models for TESH-Query v2 AI SQL Compiler.
"""

from typing import Any, Dict, List

from pydantic import BaseModel


class QueryPlan(BaseModel):
    """Stage 1 output: structured plan describing what the SQL query should do."""

    tables: List[str]
    filters: List[str]
    aggregations: List[str]
    joins_needed: List[str]


class SQLQuery(BaseModel):
    """Stage 2 output: structured SQL query with named parameters."""

    query: str
    parameters: Dict[str, Any]
