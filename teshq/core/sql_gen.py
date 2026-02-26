"""
Stage 2 SQL Generator for TESH-Query v2.

Takes a QueryPlan and compressed schema, then generates a structured SQLQuery
using deterministic LLM settings and structured output mode.
No regex fallback. No manual JSON parsing.
"""

import time
from typing import Any, Optional

from langchain_core.prompts import ChatPromptTemplate

from teshq.core.models import QueryPlan, SQLQuery
from teshq.utils.logging import logger

_SYSTEM_PROMPT = """You are a production-grade SQL generator.

Schema format: TABLE name (col TYPE [PK] [NN] [FK→other_table.col], ...)
  PK = primary key, NN = not null, FK→ = foreign key pointing to another table/column.

Generation rules:
- Use ANSI SQL unless the schema comment specifies a dialect (e.g. PostgreSQL, MySQL).
- Use :param_name placeholders for all user-supplied literal values.
- Use explicit column names — never SELECT *.
- Use table aliases for every table in multi-table queries.
- Follow FK→ annotations to determine correct JOIN columns.
- Prefer INNER JOIN unless an outer join is clearly required.
- For aggregations, always include a GROUP BY clause.
- ORDER BY requires an explicit column; never ORDER BY a bare number.
- Default to SELECT; only use INSERT/UPDATE/DELETE when the query explicitly requests it.
- Never emit DROP, TRUNCATE, or ALTER statements.
- If the query is ambiguous, choose the safest, most read-only interpretation.

Output only the structured SQLQuery — no markdown, no explanation."""

_HUMAN_TEMPLATE = (
    "Schema (with relationship annotations):\n{schema}\n\n"
    "Query plan:\n"
    "  Tables: {tables}\n"
    "  Filters: {filters}\n"
    "  Aggregations: {aggregations}\n"
    "  Joins: {joins}\n\n"
    "Natural language request: {nl_query}\n\n"
    "Generate a single SQL statement that answers the request."
)


class SQLGenerator:
    """
    LLM-based SQL generator (Stage 2 of two-stage SQL generation).

    Uses structured output mode with temperature=0 for deterministic results.
    Accepts any LangChain BaseChatModel (Gemini, Azure OpenAI, etc.).
    """

    def __init__(self, llm: Any):
        self._llm = llm
        self._structured_llm = llm.with_structured_output(SQLQuery)
        self._prompt = ChatPromptTemplate.from_messages(
            [
                ("system", _SYSTEM_PROMPT),
                ("human", _HUMAN_TEMPLATE),
            ]
        )

    def generate(self, nl_query: str, schema: str, plan: QueryPlan) -> SQLQuery:
        """
        Generate a structured SQLQuery from the plan and compressed schema.

        Args:
            nl_query: User's natural language query.
            schema: Compressed schema string for the relevant tables.
            plan: QueryPlan from Stage 1.

        Returns:
            A populated SQLQuery instance.
        """
        start = time.time()
        logger.info("Starting SQL generation", query_length=len(nl_query))

        try:
            messages = self._prompt.format_messages(
                schema=schema,
                tables=", ".join(plan.tables),
                filters="; ".join(plan.filters) if plan.filters else "none",
                aggregations="; ".join(plan.aggregations) if plan.aggregations else "none",
                joins="; ".join(plan.joins_needed) if plan.joins_needed else "none",
                nl_query=nl_query,
            )
            sql_query: SQLQuery = self._structured_llm.invoke(messages)
            elapsed_ms = int((time.time() - start) * 1000)
            logger.success(
                "SQL query generated",
                sql_latency_ms=elapsed_ms,
                query_length=len(sql_query.query),
            )
            return sql_query
        except Exception as e:
            elapsed_ms = int((time.time() - start) * 1000)
            logger.error("SQL generation failed", error=e, sql_latency_ms=elapsed_ms)
            raise


def build_sql_generator(
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    provider: str = "google",
    **kwargs: Any,
) -> SQLGenerator:
    """
    Create an SQLGenerator backed by a deterministic LLM.

    Args:
        api_key:   API key for the chosen provider (falls back to env var).
        model_name: Model/deployment name.
        provider:  ``"google"`` (Gemini) or ``"azure"`` (Azure OpenAI).
        **kwargs:  Extra keyword arguments forwarded to ``build_llm()``.

    Returns:
        Configured SQLGenerator.
    """
    from teshq.core.llm_factory import build_llm

    llm = build_llm(
        provider=provider,
        api_key=api_key,
        model_name=model_name,
        temperature=0,
        top_p=1,
        top_k=1,
        **kwargs,
    )
    return SQLGenerator(llm)

