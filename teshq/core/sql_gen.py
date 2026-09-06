"""
Stage 2 SQL Generator for TESH-Query v2.

Takes a QueryPlan and compressed schema, then generates a structured SQLQuery
using deterministic LLM settings and structured output mode.
No regex fallback. No manual JSON parsing.
"""

import json
import time
from typing import Any, Optional

from langchain_core.prompts import ChatPromptTemplate

from teshq.core.dialect import SQLDialect, detect_dialect, get_dialect_rules
from teshq.core.models import QueryPlan, SQLQuery
from teshq.utils.logging import logger


_SYSTEM_PROMPT_TEMPLATE = """You are a production-grade SQL generator targeting a {dialect} database.

Schema format: TABLE name (col TYPE [PK] [NN] [FK→other_table.col], ...)
  PK = primary key, NN = not null, FK→ = foreign key pointing to another table/column.

Generation rules:
- Generate ONLY valid {dialect} SQL syntax. Do NOT use syntax from other databases.
- Embed literal values directly in the SQL. Do NOT use :param_name placeholders or bind parameters.
- Select ONLY the columns the user explicitly asked for — nothing more, nothing less. Do not add extra columns like IDs unless the user requested them.
- EXCEPTION: When the user asks to "show all", "list all", or "display all" from a table without specifying particular columns, include ALL columns from the primary table.
- Use explicit column names — never SELECT *.
- Use table aliases for every table in multi-table queries.
- Follow FK→ annotations to determine correct JOIN columns.
- Prefer INNER JOIN unless an outer join is clearly required.
- For aggregations, the GROUP BY clause must contain ONLY the non-aggregated columns that appear in the SELECT clause. Do NOT add extra columns (like IDs) to GROUP BY if they are not in the SELECT.
- ORDER BY requires an explicit column; never ORDER BY a bare number.
- Default to SELECT; only use INSERT/UPDATE/DELETE when the query explicitly requests it.
- Never emit DROP, TRUNCATE, or ALTER statements.
- If the query is ambiguous, choose the safest, most read-only interpretation.
- Do NOT add column aliases (AS ...) unless the user explicitly asks for renamed columns.
{dialect_rules}
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

    def __init__(self, llm: Any, provider: str = "google", dialect: Optional[SQLDialect] = None):
        self._llm = llm
        self._provider = provider.lower()
        self._dialect = dialect or SQLDialect.GENERIC

        # Build the dialect-aware system prompt
        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            dialect=str(self._dialect),
            dialect_rules=get_dialect_rules(self._dialect),
        )

        # Azure OpenAI's strict JSON Schema mode rejects Dict[str, Any].
        # For Azure we do a plain chat invocation + manual JSON parsing.
        # For Google Gemini we use with_structured_output (Pydantic schema).
        if self._provider != "azure":
            self._structured_llm = llm.with_structured_output(SQLQuery)
        else:
            self._structured_llm = None  # unused for Azure
            # Create a plain LLM instance that does NOT use response_format,
            # avoiding both the strict schema and json_object restriction.
            try:
                self._plain_llm = llm.bind(response_format={"type": "text"})
            except Exception:
                self._plain_llm = llm
        self._prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", _HUMAN_TEMPLATE),
            ]
        )

    def generate(self, nl_query: str, schema: str, plan: QueryPlan, error_hint: Optional[str] = None, callbacks: Optional[list] = None) -> SQLQuery:
        """
        Generate a structured SQLQuery from the plan and compressed schema.

        Args:
            nl_query: User's natural language query.
            schema: Compressed schema string for the relevant tables.
            plan: QueryPlan from Stage 1.
            error_hint: Optional previous execution error to inject as a correction hint.

        Returns:
            A populated SQLQuery instance.
        """
        start = time.time()
        logger.info("Starting SQL generation", query_length=len(nl_query))

        messages = self._prompt.format_messages(
            schema=schema,
            tables=", ".join(plan.tables),
            filters="; ".join(plan.filters) if plan.filters else "none",
            aggregations="; ".join(plan.aggregations) if plan.aggregations else "none",
            joins="; ".join(plan.joins_needed) if plan.joins_needed else "none",
            nl_query=nl_query,
        )
        # If a previous execution error is provided, inject it as a correction hint
        if error_hint:
            from langchain_core.messages import HumanMessage
            messages.append(HumanMessage(
                content=f"The previous SQL attempt raised the following error:\n{error_hint}\n\n"
                        "Please fix the SQL to avoid this error."
            ))

        max_attempts = 3
        last_exc: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            try:
                if self._provider == "azure":
                    sql_query = self._invoke_azure(messages, callbacks)
                else:
                    sql_query = self._structured_llm.invoke(messages, config={"callbacks": callbacks} if callbacks else None)

                elapsed_ms = int((time.time() - start) * 1000)
                logger.success(
                    "SQL query generated",
                    sql_latency_ms=elapsed_ms,
                    query_length=len(sql_query.query),
                )
                return sql_query

            except Exception as e:
                last_exc = e
                exc_name = type(e).__name__
                # Retry transient parse/validation failures
                if any(
                    n in exc_name
                    for n in ("OutputParserException", "ValidationError", "JSONDecodeError", "ValueError")
                ) and attempt < max_attempts:
                    logger.warning(
                        f"SQL generation parse error (attempt {attempt}/{max_attempts}) — retrying",
                        error=e,
                    )
                    continue
                # Non-retryable or exhausted
                break

        elapsed_ms = int((time.time() - start) * 1000)
        logger.error("SQL generation failed", error=last_exc, sql_latency_ms=elapsed_ms)
        raise last_exc  # type: ignore[misc]


    def _invoke_azure(self, messages, callbacks: Optional[list] = None) -> SQLQuery:
        """
        Invoke the LLM without structured output for Azure OpenAI compatibility.

        Uses a plain text response (no response_format schema) and manually
        parses the resulting JSON into a SQLQuery model.
        """
        start = time.time()
        from langchain_core.messages import HumanMessage

        dialect_str = str(self._dialect)
        json_instruction = HumanMessage(
            content=(
                f"IMPORTANT: You are generating {dialect_str} SQL. "
                f"Use ONLY {dialect_str}-compatible syntax.\n"
                "Embed all literal values directly in the SQL — do NOT use :param_name placeholders.\n"
                "Select ONLY the columns the user asked for — no extra columns.\n\n"
                "Output your answer as a JSON object with exactly two keys: "
                "\"query\" (the SQL string) and \"parameters\" (an object, always {{}}).\n"
                "Example: {{\"query\": \"SELECT ...\", \"parameters\": {{}}}}\n"
                "No markdown, no explanation — raw JSON only."
            )
        )
        response = self._plain_llm.invoke(messages + [json_instruction], config={"callbacks": callbacks} if callbacks else None)
        raw = response.content.strip()

        # Strip accidental markdown fences
        if "```" in raw:
            import re as _re
            raw = _re.sub(r"```(?:json)?\n?", "", raw).replace("```", "").strip()

        data = json.loads(raw)
        return SQLQuery(
            query=data["query"],
            parameters=data.get("parameters", {}),
        )


def build_sql_generator(
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    provider: str = "google",
    dialect: Optional[SQLDialect] = None,
    **kwargs: Any,
) -> SQLGenerator:
    """
    Create an SQLGenerator backed by a deterministic LLM.

    Args:
        api_key:   API key for the chosen provider (falls back to env var).
        model_name: Model/deployment name.
        provider:  ``"google"`` (Gemini) or ``"azure"`` (Azure OpenAI).
        dialect:   Target SQL dialect. Auto-detected from DB URL if not given.
        **kwargs:  Extra keyword arguments forwarded to ``build_llm()``.

    Returns:
        Configured SQLGenerator.
    """
    from teshq.core.llm_factory import build_llm

    # Auto-detect dialect if not explicitly provided
    if dialect is None:
        dialect = detect_dialect()

    llm = build_llm(
        provider=provider,
        api_key=api_key,
        model_name=model_name,
        temperature=0,
        top_p=1,
        top_k=1,
        **kwargs,
    )
    return SQLGenerator(llm, provider=provider, dialect=dialect)
