"""
Stage 1 Query Planner for TESH-Query v2.

Calls the LLM with a compressed schema and natural language query to
produce a structured QueryPlan describing what tables, filters,
aggregations, and joins will be needed — without generating SQL yet.
"""

import time
from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from teshq.core.models import QueryPlan
from teshq.utils.logging import logger

_SYSTEM_PROMPT = (
    "You analyze natural language queries. "
    "Return structured JSON describing: "
    "tables required, filters, aggregations, joins needed. "
    "Do not generate SQL."
)

_HUMAN_TEMPLATE = "Schema:\n{schema}\n\nQuery: {nl_query}"


class QueryPlanner:
    """
    LLM-based query planner (Stage 1 of two-stage SQL generation).

    Uses structured output mode with temperature=0 for deterministic results.
    """

    def __init__(self, llm: ChatGoogleGenerativeAI):
        self._llm = llm
        self._structured_llm = llm.with_structured_output(QueryPlan)
        self._prompt = ChatPromptTemplate.from_messages(
            [
                ("system", _SYSTEM_PROMPT),
                ("human", _HUMAN_TEMPLATE),
            ]
        )

    def plan(self, nl_query: str, schema: str) -> QueryPlan:
        """
        Produce a QueryPlan from a natural language query and compressed schema.

        Args:
            nl_query: User's natural language query.
            schema: Compressed schema string from SchemaGraph.

        Returns:
            A populated QueryPlan instance.
        """
        start = time.time()
        logger.info("Starting query planning", query_length=len(nl_query))

        try:
            messages = self._prompt.format_messages(schema=schema, nl_query=nl_query)
            plan: QueryPlan = self._structured_llm.invoke(messages)
            elapsed_ms = int((time.time() - start) * 1000)
            logger.success(
                "Query plan generated",
                tables=plan.tables,
                plan_latency_ms=elapsed_ms,
            )
            return plan
        except Exception as e:
            elapsed_ms = int((time.time() - start) * 1000)
            logger.error("Query planning failed", error=e, plan_latency_ms=elapsed_ms)
            raise


def build_planner(api_key: str, model_name: str) -> QueryPlanner:
    """
    Create a QueryPlanner backed by a deterministic LLM.

    Args:
        api_key: Google Gemini API key.
        model_name: Gemini model identifier.

    Returns:
        Configured QueryPlanner.
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
    return QueryPlanner(llm)
