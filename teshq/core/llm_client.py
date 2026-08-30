"""
Unified LLM Client Abstraction for TESH-Query.

Provides a common interface (LLMClient) for both cloud backends (Gemini, Azure)
and the local in-process GGUF inference backend.
"""

from typing import Protocol, Optional, Iterator, Dict, Any, List
from teshq.core.models import QueryPlan, SQLQuery
from teshq.core.planner import QueryPlanner, build_planner
from teshq.core.sql_gen import SQLGenerator, build_sql_generator
from teshq.core.inference import InferenceRuntime, InferenceConfig
from teshq.core.grammar import get_sql_grammar
from teshq.utils.logging import logger

class LLMClient(Protocol):
    """Unified protocol defining operations for generating query plans and SQL."""
    
    def generate_plan(self, nl_query: str, schema: str, callbacks: Optional[List[Any]] = None) -> QueryPlan:
        """Produce a structured QueryPlan (Stage 1)."""
        ...
        
    def generate_sql(
        self, 
        nl_query: str, 
        schema: str, 
        plan: QueryPlan, 
        error_hint: Optional[str] = None, 
        callbacks: Optional[List[Any]] = None
    ) -> SQLQuery:
        """Produce a structured SQLQuery statement (Stage 2)."""
        ...

    def get_token_tracker(self) -> Dict[str, int]:
        """Return the accumulated token usage counters."""
        ...


class CloudLLMClient(LLMClient):
    """
    Wraps cloud providers (Gemini, Azure OpenAI) using LangChain.
    Runs the canonical two-stage (Plan -> Generate) workflow.
    """
    def __init__(self, planner: QueryPlanner, sql_gen: SQLGenerator):
        self._planner = planner
        self._sql_gen = sql_gen
        self._prompt_tokens = 0
        self._completion_tokens = 0

    def generate_plan(self, nl_query: str, schema: str, callbacks: Optional[List[Any]] = None) -> QueryPlan:
        return self._planner.plan(nl_query, schema, callbacks=callbacks)

    def generate_sql(
        self, 
        nl_query: str, 
        schema: str, 
        plan: QueryPlan, 
        error_hint: Optional[str] = None, 
        callbacks: Optional[List[Any]] = None
    ) -> SQLQuery:
        return self._sql_gen.generate(nl_query, schema, plan, error_hint=error_hint, callbacks=callbacks)

    def get_token_tracker(self) -> Dict[str, int]:
        # Tokens are tracked via LangChain callbacks in the query engine
        return {}


def _detect_dialect(db_url: str) -> str:
    """Detect SQL dialect from the database URL for use in prompts."""
    url = db_url.lower()
    if url.startswith("sqlite"):
        return "SQLite"
    elif url.startswith("postgresql") or url.startswith("postgres"):
        return "PostgreSQL"
    elif url.startswith("mysql") or url.startswith("mariadb"):
        return "MySQL"
    elif url.startswith("mssql") or url.startswith("sqlserver"):
        return "SQL Server (T-SQL)"
    elif url.startswith("oracle"):
        return "Oracle"
    return "SQL"


def _dialect_hints(dialect: str) -> str:
    """Return dialect-specific function hints to help small local models."""
    hints = {
        "SQLite": (
            "SQLite function reference:\n"
            "- Date difference in days: CAST(julianday(date2) - julianday(date1) AS INTEGER)\n"
            "- Current date: DATE('now')\n"
            "- Date parts: strftime('%Y', date_col), strftime('%m', date_col)\n"
            "- String concat: col1 || col2 (no CONCAT function)\n"
            "- IFNULL(x, y) instead of COALESCE for two args\n"
            "- No DATEDIFF, DATEADD, YEAR(), MONTH(), DAY() functions\n"
            "- List tables: SELECT name FROM sqlite_master WHERE type='table'\n"
        ),
        "PostgreSQL": (
            "PostgreSQL function reference:\n"
            "- Date difference: (date2 - date1) returns interval, or DATE_PART('day', date2 - date1)\n"
            "- Current date: CURRENT_DATE\n"
            "- String concat: col1 || col2 or CONCAT(col1, col2)\n"
        ),
        "MySQL": (
            "MySQL function reference:\n"
            "- Date difference in days: DATEDIFF(date2, date1)\n"
            "- Current date: CURDATE() or CURRENT_DATE\n"
            "- Date parts: YEAR(date_col), MONTH(date_col), DAY(date_col)\n"
        ),
    }
    return hints.get(dialect, "")


class LocalLLMClient(LLMClient):
    """
    Runs in-process LLM inference using llama-cpp-python.
    Uses a grammar-constrained, single-shot generation to save local compute/tokens.
    """
    def __init__(self, runtime: InferenceRuntime, config: InferenceConfig, db_url: str = ""):
        self._runtime = runtime
        self._config = config
        self._grammar = get_sql_grammar()
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._dialect = _detect_dialect(db_url) if db_url else "SQL"

    def generate_plan(self, nl_query: str, schema: str, callbacks: Optional[List[Any]] = None) -> QueryPlan:
        """Local mode bypasses the expensive Stage 1 LLM planner."""
        logger.info("Local mode: skipping LLM planning stage to save tokens.")
        return QueryPlan(tables=[], filters=[], aggregations=[], joins_needed=[])

    def generate_sql(
        self, 
        nl_query: str, 
        schema: str, 
        plan: QueryPlan, 
        error_hint: Optional[str] = None, 
        callbacks: Optional[List[Any]] = None
    ) -> SQLQuery:
        """Generates SQL using grammar constraints and custom local prompt."""
        self._runtime.load(self._config)
        
        hints = _dialect_hints(self._dialect)
        system_prompt = (
            f"You are a strict text-to-SQL assistant targeting a {self._dialect} database. "
            "CRITICAL RULES:\n"
            f"1. Generate ONLY a valid {self._dialect} SQL statement.\n"
            "2. Use ONLY the exact table and column names provided in the schema below. Do NOT invent or guess column names.\n"
            "3. Do not use syntax or functions from other database engines.\n"
            "4. Do not include markdown formatting or explanations.\n"
            "5. When JOINing tables, use ONLY the FK→ relationships shown in the schema. "
            "For example, if order_items has 'order_id FK→orders.order_id', join order_items to orders on order_id.\n"
            "6. If two tables are not directly linked by FK, join through an intermediate table. "
            "For example: customers → orders (via customer_id) → order_items (via order_id).\n"
            "7. If you JOIN the same table more than once, give each instance a unique alias "
            "(e.g., order_items oi1, order_items oi2) and reference columns through those aliases."
        )
        if hints:
            system_prompt += f"\n\n{hints}"
        
        prompt = f"Database Schema:\n{schema}\n\nNatural Language Request: {nl_query}\n\n"
        if error_hint:
            prompt += (
                f"IMPORTANT: The previous SQL attempt failed with this error:\n{error_hint}\n"
                "You MUST fix the error. Re-read the schema above carefully and use only the exact column names listed.\n\n"
            )
        prompt += "SQL Query:"

        res = self._runtime.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=512,
            temperature=0.0,
            grammar=self._grammar,
        )
        
        # Accumulate tokens
        self._prompt_tokens += res.prompt_tokens
        self._completion_tokens += res.completion_tokens
        
        # Clean up any potential markdown wraps
        cleaned_query = res.text.strip()
        if cleaned_query.startswith("```"):
            lines = cleaned_query.splitlines()
            if lines[0].startswith("```sql") or lines[0].startswith("```"):
                cleaned_query = "\n".join(lines[1:-1]).strip()
        
        # Fake callback updates if custom tracker callback provided
        if callbacks:
            for cb in callbacks:
                # Update TokenTracker if present
                if hasattr(cb, "prompt_tokens") and hasattr(cb, "completion_tokens"):
                    cb.prompt_tokens += res.prompt_tokens
                    cb.completion_tokens += res.completion_tokens

        return SQLQuery(query=cleaned_query, parameters={})

    def get_token_tracker(self) -> Dict[str, int]:
        return {
            "prompt_tokens": self._prompt_tokens,
            "completion_tokens": self._completion_tokens,
            "total_tokens": self._prompt_tokens + self._completion_tokens,
        }
