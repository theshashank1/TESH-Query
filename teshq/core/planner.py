"""
Stage 1 Query Planner for TESH-Query v2.

Calls the LLM with a compressed schema and natural language query to
produce a structured QueryPlan describing what tables, filters,
aggregations, and joins will be needed — without generating SQL yet.
"""

import time
from typing import Any, Optional

from langchain_core.prompts import ChatPromptTemplate

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
    Accepts any LangChain BaseChatModel (Gemini, Azure OpenAI, etc.).
    """

    def __init__(self, llm: Any):
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


def build_planner(
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    provider: str = "google",
    **kwargs: Any,
) -> QueryPlanner:
    """
    Create a QueryPlanner backed by a deterministic LLM.

    Args:
        api_key:   API key for the chosen provider (falls back to env var).
        model_name: Model/deployment name.
        provider:  ``"google"`` (Gemini) or ``"azure"`` (Azure OpenAI).
        **kwargs:  Extra keyword arguments forwarded to ``build_llm()``.

    Returns:
        Configured QueryPlanner.
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
    return QueryPlanner(llm)

