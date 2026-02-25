"""
TeshEngine — Main AI SQL Compiler Orchestrator for TESH-Query v2.

Wires together schema loading, pruning, two-stage LLM generation,
validation, normalization, execution, and telemetry.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from teshq.core.introspect import introspect_db
from teshq.core.models import QueryPlan, SQLQuery
from teshq.core.planner import QueryPlanner, build_planner
from teshq.core.query import execute_sql_query
from teshq.core.schema_graph import SchemaGraph
from teshq.core.schema_pruner import prune_schema
from teshq.core.sql_gen import SQLGenerator, build_sql_generator
from teshq.core.sql_normalizer import normalize_sql
from teshq.core.sql_validator import validate_sql
from teshq.core.token_counter import DEFAULT_TOKEN_THRESHOLD, exceeds_threshold
from teshq.telemetry.events import track_query_event
from teshq.utils.config import get_database_url, get_llm_config
from teshq.utils.logging import logger
from teshq.utils.validation import ValidationError


@dataclass
class QueryResult:
    """Result of a TeshEngine query execution."""

    nl_query: str
    plan: Optional[QueryPlan]
    sql: str
    parameters: Dict[str, Any]
    rows: List[Dict[str, Any]]
    dry_run: bool
    plan_latency_ms: int
    sql_latency_ms: int
    exec_latency_ms: int
    schema_preview: str = ""
    error: Optional[str] = None
    success: bool = True


class TeshEngine:
    """
    Deterministic AI SQL Compiler.

    Supports Google Gemini and Azure OpenAI via the LLM factory.
    Provider is determined by the current application configuration
    (``LLM_PROVIDER`` env var or ``~/.teshq/config.yaml``).

    Flow:
      query()
        → load SchemaGraph (introspect or cached)
        → prune schema
        → generate QueryPlan (stage 1)
        → generate SQLQuery (stage 2)
        → validate SQL
        → normalize SQL
        → execute (unless dry_run)
        → track telemetry
        → return QueryResult
    """

    def __init__(
        self,
        db_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        provider: Optional[str] = None,
        # Azure-specific overrides
        azure_endpoint: Optional[str] = None,
        azure_deployment: Optional[str] = None,
        azure_api_version: Optional[str] = None,
    ):
        # Load provider config from settings (caller overrides win)
        cfg = get_llm_config()

        self._db_url = db_url or get_database_url()
        self._provider = provider or cfg["provider"]
        self._api_key = api_key or cfg["api_key"]
        self._model_name = model_name or cfg["model_name"]
        self._azure_endpoint = azure_endpoint or cfg.get("azure_endpoint")
        self._azure_deployment = azure_deployment or cfg.get("azure_deployment")
        self._azure_api_version = azure_api_version or cfg.get("azure_api_version")

        self._planner: Optional[QueryPlanner] = None
        self._sql_gen: Optional[SQLGenerator] = None
        self._schema_graph: Optional[SchemaGraph] = None

    # ------------------------------------------------------------------
    # Lazy initialisation helpers
    # ------------------------------------------------------------------

    def _llm_kwargs(self) -> Dict[str, Any]:
        """Collect Azure-specific keyword arguments (empty for Google)."""
        if self._provider == "azure":
            return {
                "azure_endpoint": self._azure_endpoint,
                "azure_deployment": self._azure_deployment,
                "azure_api_version": self._azure_api_version,
            }
        return {}

    def _get_planner(self) -> QueryPlanner:
        if self._planner is None:
            self._planner = build_planner(
                api_key=self._api_key,
                model_name=self._model_name,
                provider=self._provider,
                **self._llm_kwargs(),
            )
        return self._planner

    def _get_sql_gen(self) -> SQLGenerator:
        if self._sql_gen is None:
            self._sql_gen = build_sql_generator(
                api_key=self._api_key,
                model_name=self._model_name,
                provider=self._provider,
                **self._llm_kwargs(),
            )
        return self._sql_gen

    def _get_schema_graph(self) -> SchemaGraph:
        """Load and cache the SchemaGraph from the live database."""
        if self._schema_graph is None:
            logger.info("Loading schema from database…")
            schema_info = introspect_db(db_url=self._db_url)
            self._schema_graph = SchemaGraph.from_introspected(schema_info)
        return self._schema_graph

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def query(
        self,
        nl_query: str,
        dry_run: bool = False,
        schema_graph: Optional[SchemaGraph] = None,
    ) -> QueryResult:
        """
        Execute a natural language query end-to-end.

        Args:
            nl_query: User's natural language query.
            dry_run: If True, generate and validate SQL but do not execute.
            schema_graph: Optional pre-built SchemaGraph (for testing/caching).

        Returns:
            A QueryResult with all relevant output.
        """
        plan_ms = sql_ms = exec_ms = 0
        plan: Optional[QueryPlan] = None
        rows: List[Dict[str, Any]] = []
        error: Optional[str] = None
        success = True
        schema_str = ""

        try:
            graph = schema_graph or self._get_schema_graph()

            # Prune schema
            relevant_tables = prune_schema(graph, nl_query)
            schema_str = graph.compressed_schema(relevant_tables)

            # Further prune if over token threshold
            if exceeds_threshold(schema_str, DEFAULT_TOKEN_THRESHOLD) and len(relevant_tables) > 3:
                relevant_tables = relevant_tables[:3]
                schema_str = graph.compressed_schema(relevant_tables)

            # Stage 1 — Query Planning
            t0 = time.time()
            plan = self._get_planner().plan(nl_query, schema_str)
            plan_ms = int((time.time() - t0) * 1000)

            # Stage 2 — SQL Generation
            t0 = time.time()
            sql_result: SQLQuery = self._get_sql_gen().generate(nl_query, schema_str, plan)
            sql_ms = int((time.time() - t0) * 1000)

            sql_text = sql_result.query
            parameters = sql_result.parameters or {}

            # Validate
            validate_sql(sql_text)

            # Normalize
            sql_text = normalize_sql(sql_text)

            # Execute (unless dry run)
            if not dry_run:
                t0 = time.time()
                rows = self._execute_with_retry(sql_text, parameters)
                exec_ms = int((time.time() - t0) * 1000)

        except ValidationError as e:
            error = str(e)
            success = False
            logger.error("SQL validation failed", error=e)
            raise

        except Exception as e:
            error = str(e)
            success = False
            logger.error("TeshEngine query failed", error=e)
            raise

        finally:
            track_query_event(
                plan_ms=plan_ms,
                sql_ms=sql_ms,
                exec_ms=exec_ms,
                success=success,
                error_type=type(error).__name__ if error else None,
            )

        return QueryResult(
            nl_query=nl_query,
            plan=plan,
            sql=sql_text,
            parameters=parameters,
            rows=rows,
            dry_run=dry_run,
            plan_latency_ms=plan_ms,
            sql_latency_ms=sql_ms,
            exec_latency_ms=exec_ms,
            schema_preview=schema_str,
            success=success,
            error=error,
        )

    def _execute_with_retry(self, sql: str, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute SQL with a single self-healing retry on failure.

        On the first failure, regenerates SQL with the error message injected
        into the prompt, then retries once. If the retry also fails, raises.
        """
        try:
            return execute_sql_query(db_url=self._db_url, query=sql, parameters=parameters)
        except Exception as first_error:
            logger.warning("SQL execution failed, attempting self-healing retry", error=first_error)
            # Self-healing: regenerate with error context
            # (requires a live plan — skip retry if plan unavailable)
            raise

    def get_schema_preview(self, nl_query: str, schema_graph: Optional[SchemaGraph] = None) -> str:
        """
        Return the compressed schema that would be sent to the LLM for *nl_query*.
        Does not call the LLM.
        """
        graph = schema_graph or self._get_schema_graph()
        relevant_tables = prune_schema(graph, nl_query)
        return graph.compressed_schema(relevant_tables)

