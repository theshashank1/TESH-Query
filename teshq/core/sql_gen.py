"""
Stage 2 SQL Generator for TESH-Query v2.

Takes a QueryPlan and compressed schema, then generates a structured SQLQuery
using deterministic LLM settings and structured output mode.
No regex fallback. No manual JSON parsing.
"""

import time

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from teshq.core.models import QueryPlan, SQLQuery
from teshq.utils.logging import logger

_SYSTEM_PROMPT = """You convert natural language to SQL.

Rules:
- ANSI SQL unless schema specifies dialect
- Use :param_name for values
- SELECT by default
- Only INSERT/UPDATE/DELETE if explicitly requested
- Never DROP, TRUNCATE, ALTER
- Use table aliases in joins
- Never use SELECT *
Output only structured SQLQuery."""

_HUMAN_TEMPLATE = (
    "Schema:\n{schema}\n\n"
    "Plan:\nTables: {tables}\nFilters: {filters}\n"
    "Aggregations: {aggregations}\nJoins: {joins}\n\n"
    "Query: {nl_query}"
)


class SQLGenerator:
    """
    LLM-based SQL generator (Stage 2 of two-stage SQL generation).

    Uses structured output mode with temperature=0 for deterministic results.
    """

    def __init__(self, llm: ChatGoogleGenerativeAI):
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


def build_sql_generator(api_key: str, model_name: str) -> SQLGenerator:
    """
    Create an SQLGenerator backed by a deterministic LLM.

    Args:
        api_key: Google Gemini API key.
        model_name: Gemini model identifier.

    Returns:
        Configured SQLGenerator.
    """
    import os

    if not os.getenv("GOOGLE_API_KEY") and api_key:
        os.environ["GOOGLE_API_KEY"] = api_key

    llm = ChatGoogleGenerativeAI(
        model=model_name,
        temperature=0,
        top_p=1,
        top_k=1,
    )
    return SQLGenerator(llm)
