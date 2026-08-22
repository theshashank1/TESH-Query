"""
Stage 1 Query Planner for TESH-Query v2.

Calls the LLM with a compressed schema and natural language query to
produce a structured QueryPlan describing what tables, filters,
aggregations, and joins will be needed — without generating SQL yet.
"""

import json
import re
import time
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate

from teshq.core.models import QueryPlan
from teshq.utils.logging import logger

_SYSTEM_PROMPT = (
    "You are a database query analyst. "
    "Given a compressed database schema and a natural language query, identify:\n"
    "  - tables: all table names needed to answer the query\n"
    "  - filters: WHERE clause conditions (e.g. 'age > 25', 'status = active')\n"
    "  - aggregations: GROUP BY / aggregate functions needed (e.g. 'COUNT orders', 'SUM revenue')\n"
    "  - joins_needed: relationships to traverse (e.g. 'users.id = orders.user_id')\n"
    "Use the FK→ annotations in the schema to identify join paths. "
    "Do NOT generate any SQL — return structured JSON only.\n\n"
    "Respond with ONLY valid JSON in this exact format:\n"
    '{"tables": [...], "filters": [...], "aggregations": [...], "joins_needed": [...]}'
    .replace("{", "{{").replace("}", "}}")
)

_HUMAN_TEMPLATE = (
    "Schema (TABLE name (col TYPE flags, ...) where PK=primary key, NN=not null, FK→table.col=foreign key):\n"
    "{schema}\n\n"
    "Query: {nl_query}"
)

# Regex to strip markdown code fences (```json ... ```)
_MD_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class QueryPlanner:
    """
    LLM-based query planner (Stage 1 of two-stage SQL generation).

    Uses structured output mode (Google) or plain JSON parse (Azure) for
    deterministic results. Accepts any LangChain BaseChatModel.
    """

    def __init__(self, llm: Any, provider: str = "google") -> None:
        self._llm = llm
        self._provider = provider.lower().strip()
        self._prompt = ChatPromptTemplate.from_messages(
            [
                ("system", _SYSTEM_PROMPT),
                ("human", _HUMAN_TEMPLATE),
            ]
        )

        # Google: use structured output via Pydantic schema
        # Azure: skip structured output (unreliable with List[str] fields on strict mode)
        if self._provider != "azure":
            self._structured_llm = llm.with_structured_output(QueryPlan)
        else:
            self._structured_llm = None

    def plan(self, nl_query: str, schema: str, callbacks: Optional[list] = None) -> QueryPlan:
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

        messages = self._prompt.format_messages(schema=schema, nl_query=nl_query)

        if self._provider == "azure":
            plan = self._invoke_azure(messages, start, callbacks)
        else:
            plan = self._invoke_google(messages, start, callbacks)

        return plan

    def _invoke_google(self, messages: list, start: float, callbacks: Optional[list] = None) -> QueryPlan:
        """Invoke via structured output (Pydantic schema) for Google Gemini."""
        max_attempts = 3
        last_exc: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            try:
                plan: QueryPlan = self._structured_llm.invoke(messages, config={"callbacks": callbacks} if callbacks else None)
                elapsed_ms = int((time.time() - start) * 1000)
                logger.success(
                    "Query plan generated",
                    tables=plan.tables,
                    plan_latency_ms=elapsed_ms,
                )
                return plan
            except Exception as e:
                last_exc = e
                # Retry on parse / validation failures, not on hard errors
                exc_name = type(e).__name__
                if any(
                    n in exc_name
                    for n in ("OutputParserException", "ValidationError", "ValueError")
                ) and attempt < max_attempts:
                    logger.warning(
                        f"Query planning parse error (attempt {attempt}/{max_attempts}) — retrying",
                        error=e,
                    )
                    continue
                # Non-retryable or exhausted
                break

        elapsed_ms = int((time.time() - start) * 1000)
        logger.error("Query planning failed", error=last_exc, plan_latency_ms=elapsed_ms)
        raise last_exc  # type: ignore[misc]

    def _invoke_azure(self, messages: list, start: float, callbacks: Optional[list] = None) -> QueryPlan:
        """
        Invoke via plain text for Azure OpenAI.

        Azure's strict JSON schema mode is unreliable with List[str] fields.
        We use a plain prompt, parse the JSON response manually, and validate
        it into a QueryPlan via model_validate().
        """
        max_attempts = 3
        last_exc: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            try:
                response = self._llm.invoke(messages, config={"callbacks": callbacks} if callbacks else None)
                content: str = response.content if hasattr(response, "content") else str(response)

                # Strip markdown code fences if present
                fence_match = _MD_FENCE_RE.search(content)
                if fence_match:
                    content = fence_match.group(1)

                data = json.loads(content.strip())
                plan = QueryPlan.model_validate(data)

                elapsed_ms = int((time.time() - start) * 1000)
                logger.success(
                    "Query plan generated (Azure)",
                    tables=plan.tables,
                    plan_latency_ms=elapsed_ms,
                )
                return plan

            except Exception as e:
                last_exc = e
                exc_name = type(e).__name__
                if any(
                    n in exc_name
                    for n in ("JSONDecodeError", "ValidationError", "ValueError", "OutputParserException")
                ) and attempt < max_attempts:
                    logger.warning(
                        f"Azure query planning parse error (attempt {attempt}/{max_attempts}) — retrying",
                        error=e,
                    )
                    continue
                break

        elapsed_ms = int((time.time() - start) * 1000)
        logger.error("Azure query planning failed", error=last_exc, plan_latency_ms=elapsed_ms)
        raise last_exc  # type: ignore[misc]


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
    return QueryPlanner(llm, provider=provider)
