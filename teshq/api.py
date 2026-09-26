"""
TESH-Query Programmatic API

This module provides a clean, easy-to-use interface for programmatic access to
TESH-Query functionality without needing to use the CLI.

Example usage:
    import teshq

    # Google Gemini (default)
    client = teshq.TeshQuery(
        db_url="postgresql://user:pass@host:port/dbname",
        gemini_api_key="your-api-key"
    )

    # Azure OpenAI
    client = teshq.TeshQuery(
        db_url="postgresql://user:pass@host:port/dbname",
        provider="azure",
        azure_api_key="your-azure-key",
        azure_endpoint="https://your-resource.openai.azure.com/",
        azure_deployment="gpt-4o",
    )

    schema = client.introspect_database()
    result = client.query("show me all users who registered last month")

    # Get results as a pandas DataFrame (recommended for data science)
    df = client.query_df("top 10 products by revenue")
    df.to_csv("report.csv", index=False)

    # Access SQL alongside results
    adv = client.query_advanced("monthly revenue by region")
    print(adv.query)   # SQL string
    df = adv.dataframe  # pandas DataFrame

    sql_info = client.generate_sql("count all active users")
    print(sql_info['query'])
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator, Callable, Dict, Iterator, List, Optional, Union

if TYPE_CHECKING:
    import pandas as pd
    from teshq.events import CancellationToken, QueryEvent
    from teshq.session import TeshChatSession

from .config.paths import SCHEMA_DIR
from .core.engine import TeshEngine
from .core.introspect import introspect_db, save_schema_to_files
from .config.loader import get_config, save_config
from .core.connection import connection_manager
from .utils.health import HealthChecker
from .utils.output import QueryResult
from .telemetry.events import track_feature


class TeshQuery:
    """
    Main programmatic interface for TESH-Query.

    Supports Google Gemini and Azure OpenAI providers. Both are selected
    automatically from config or can be passed explicitly.
    """

    def __init__(
        self,
        db_url: Optional[str] = None,
        # Bring-Your-Own-Engine & Business Context
        engine: Optional[Any] = None,
        business_context: Optional[Union[Dict[str, str], str]] = None,
        # Google Gemini params
        gemini_api_key: Optional[str] = None,
        gemini_model: Optional[str] = None,
        # Azure OpenAI params
        provider: Optional[str] = None,
        azure_api_key: Optional[str] = None,
        azure_endpoint: Optional[str] = None,
        azure_deployment: Optional[str] = None,
        azure_api_version: Optional[str] = None,
        # Misc
        auto_save_config: bool = False,
    ):
        """
        Initialize the TeshQuery client.

        Args:
            db_url: Database connection URL.
            engine: Optional pre-configured SQLAlchemy Engine instance (BYOE).
            business_context: Optional business rules, formulas, or glossary dict.
            gemini_api_key: Google Gemini API key.
            gemini_model: Gemini model name (default: from config or 'gemini-2.0-flash-lite').
            provider: 'google' or 'azure'. Auto-detected from credentials if not set.
            azure_api_key: Azure OpenAI API key.
            azure_endpoint: Azure OpenAI resource endpoint URL.
            azure_deployment: Azure OpenAI deployment/model name.
            azure_api_version: Azure OpenAI API version (default: '2024-02-01').
            auto_save_config: Whether to persist provided credentials to config files.
        """
        config = get_config()

        self._custom_engine = engine
        self.business_context = business_context

        # Resolve database URL
        if engine is not None and not db_url:
            if hasattr(engine, "url"):
                try:
                    self.db_url = engine.url.render_as_string(hide_password=False)
                except Exception:
                    self.db_url = str(engine.url)
            else:
                self.db_url = str(engine)
        else:
            self.db_url = db_url or config.get("DATABASE_URL") or None

        # Resolve provider
        self._provider = (
            provider
            or ("azure" if azure_api_key else None)
            or config.get("LLM_PROVIDER")
            or "google"
        )

        # Resolve Google credentials
        self.gemini_api_key = gemini_api_key or config.get("GEMINI_API_KEY") or None
        self.gemini_model = gemini_model or config.get("GEMINI_MODEL") or "gemini-2.0-flash-lite"

        # Resolve Azure credentials
        self.azure_api_key = azure_api_key or config.get("AZURE_OPENAI_API_KEY") or None
        self.azure_endpoint = azure_endpoint or config.get("AZURE_OPENAI_ENDPOINT") or None
        self.azure_deployment = azure_deployment or config.get("AZURE_OPENAI_DEPLOYMENT") or None
        self.azure_api_version = azure_api_version or config.get("AZURE_OPENAI_API_VERSION") or "2024-10-21"

        self.auto_save_config = auto_save_config

        # Validate required config
        if not self.db_url and self._custom_engine is None:
            raise ValueError(
                "Database URL is required (or provide engine=). Provide it via db_url=, engine=, or configure with: teshq config --db"
            )

        if self._provider == "azure":
            missing = []
            if not self.azure_api_key:
                missing.append("azure_api_key (or AZURE_OPENAI_API_KEY)")
            if not self.azure_endpoint:
                missing.append("azure_endpoint (or AZURE_OPENAI_ENDPOINT)")
            if not self.azure_deployment:
                missing.append("azure_deployment (or AZURE_OPENAI_DEPLOYMENT)")
            if missing:
                raise ValueError(
                    "Azure OpenAI requires: " + ", ".join(missing) + ". "
                    "Configure with: teshq config --azure"
                )
        else:
            if not self.gemini_api_key:
                raise ValueError(
                    "Gemini API key is required. Provide via gemini_api_key= or: teshq config --gemini"
                )

        # Lazy-initialized components
        self._engine: Optional[TeshEngine] = None
        self._schema_cache = None

        if self.auto_save_config:
            self.save_configuration()

    def save_configuration(self) -> bool:
        """Persist current configuration to config files (secrets to .env, rest to config.yaml)."""
        config_data: Dict[str, Optional[str]] = {
            "DATABASE_URL": self.db_url,
            "LLM_PROVIDER": self._provider,
        }
        if self._provider == "azure":
            config_data.update({
                "AZURE_OPENAI_API_KEY": self.azure_api_key,
                "AZURE_OPENAI_ENDPOINT": self.azure_endpoint,
                "AZURE_OPENAI_DEPLOYMENT": self.azure_deployment,
                "AZURE_OPENAI_API_VERSION": self.azure_api_version,
            })
        else:
            config_data["GEMINI_API_KEY"] = self.gemini_api_key
            config_data["GEMINI_MODEL"] = self.gemini_model
        return save_config(config_data)

    @property
    def engine(self) -> TeshEngine:
        """Lazily create and return the TeshEngine instance."""
        if self._engine is None:
            common_kwargs = {
                "engine": self._custom_engine,
                "business_context": self.business_context,
            }
            if self._provider == "azure":
                self._engine = TeshEngine(
                    db_url=self.db_url,
                    provider="azure",
                    api_key=self.azure_api_key,
                    model_name=self.azure_deployment,
                    azure_endpoint=self.azure_endpoint,
                    azure_deployment=self.azure_deployment,
                    azure_api_version=self.azure_api_version,
                    **common_kwargs,
                )
            else:
                self._engine = TeshEngine(
                    db_url=self.db_url,
                    provider="google",
                    api_key=self.gemini_api_key,
                    model_name=self.gemini_model,
                    **common_kwargs,
                )
        return self._engine

    def test_connection(self) -> bool:
        """Test the database connection. Returns True if successful."""
        return connection_manager.test_connection(self.db_url)

    def introspect_database(
        self,
        detect_relationships: bool = True,
        include_indexes: bool = True,
        include_sample_data: bool = False,
        sample_size: int = 3,
        save_to_files: bool = False,
        output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Introspect the database schema.

        Returns a dict containing tables, columns, relationships, and a data_model_summary string.
        """
        track_feature(
            "TeshQuery.introspect_database",
            detect_relationships=detect_relationships,
            include_indexes=include_indexes,
            include_sample_data=include_sample_data,
            save_to_files=save_to_files,
        )

        schema_info = introspect_db(
            db_url=self.db_url,
            detect_relationships=detect_relationships,
            include_indexes=include_indexes,
            include_sample_data=include_sample_data,
            sample_size=sample_size,
        )

        self._schema_cache = schema_info

        if save_to_files:
            save_dir = output_dir if output_dir is not None else str(SCHEMA_DIR)
            save_schema_to_files(
                schema_info,
                output_dir=save_dir,
                json_filename="schema.json",
                text_filename="schema.txt",
            )

        return schema_info

    def generate_sql(
        self,
        natural_language_query: str,
    ) -> Dict[str, Any]:
        """
        Generate SQL from natural language without executing it (dry-run).

        Returns dict with keys: 'query' (SQL string) and 'parameters' (dict).
        """
        result = self.engine.query(natural_language_query, dry_run=True)
        if not result.success:
            raise RuntimeError(f"SQL generation failed: {result.error}")
        return {"query": result.sql, "parameters": result.parameters}

    def execute_query(
        self, sql_query: str, parameters: Optional[Dict[str, Any]] = None
    ) -> QueryResult:
        """Execute a raw SQL query and return a QueryResult."""
        from teshq.core.query import execute_sql_query

        raw_results = execute_sql_query(
            db_url=self.db_url, query=sql_query, parameters=parameters or {}
        )
        return QueryResult(
            results=raw_results,
            query=sql_query,
            parameters=parameters,
        )

    def query(
        self,
        natural_language_query: str,
        output_format: str = "dataframe",
        output_path: Optional[str] = None,
        return_sql: bool = False,
        cancellation_token: Optional[Any] = None,
        event_callback: Optional[Callable[[Any], None]] = None,
        context: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """
        Full pipeline: generate SQL from natural language then execute it.

        Args:
            natural_language_query: Question in plain English.
            output_format: "dataframe" (default), "dict", "arrow", "polars", "csv", or "excel".
            output_path: File path to save if format is "csv" or "excel".
            return_sql: If True, include SQL in the response.
            cancellation_token: Optional CancellationToken to abort query execution.
            event_callback: Optional callback receiving QueryEvent instances.
            context: Optional domain or business context string.

        Returns:
            - ``pd.DataFrame`` when ``output_format="dataframe"``.
            - ``List[Dict]`` when ``output_format="dict"``.
            - ``pyarrow.Table`` when ``output_format="arrow"``.
            - ``polars.DataFrame`` when ``output_format="polars"``.
            - CSV string or saved file path when ``output_format="csv"``.
            - Saved file path when ``output_format="excel"``.
        """
        # Backwards compatibility
        if kwargs.get("return_dataframe") is True:
            output_format = "dataframe"

        track_feature(
            "TeshQuery.query",
            query_length_bucket=min(len(natural_language_query) // 50 * 50, 500),
            return_sql=return_sql,
            output_format=output_format,
        )

        engine_result = self.engine.query(
            natural_language_query,
            dry_run=False,
            cancellation_token=cancellation_token,
            event_callback=event_callback,
            context=context,
        )
        if not engine_result.success:
            raise RuntimeError(f"Query failed: {engine_result.error}")

        result = QueryResult(
            results=engine_result.rows,
            query=engine_result.sql,
            parameters=engine_result.parameters,
            natural_language_query=natural_language_query,
        )

        if output_format == "arrow":
            if return_sql:
                return {"sql": result.query, "parameters": result.parameters, "arrow": result.arrow}
            return result.arrow

        elif output_format == "polars":
            if return_sql:
                return {"sql": result.query, "parameters": result.parameters, "polars": result.polars}
            return result.polars

        elif output_format == "csv":
            df = result.dataframe
            if output_path:
                df.to_csv(output_path, index=False)
                return output_path
            return df.to_csv(index=False)
        
        elif output_format == "excel":
            df = result.dataframe
            if not output_path:
                raise ValueError("output_path is required when output_format='excel'.")
            df.to_excel(output_path, index=False)
            return output_path
            
        elif output_format == "dict":
            if return_sql:
                return result.to_dict(include_sql=True)
            return result.results
            
        else: # dataframe
            df = result.dataframe
            if return_sql:
                return {"sql": result.query, "parameters": result.parameters, "dataframe": df}
            return df

    def query_df(
        self,
        natural_language_query: str,
        cancellation_token: Optional[Any] = None,
        event_callback: Optional[Callable[[Any], None]] = None,
        context: Optional[str] = None,
        **kwargs,
    ) -> "pd.DataFrame":
        """
        Convert a natural language question directly into a pandas DataFrame.
        """
        track_feature(
            "TeshQuery.query_df",
            query_length_bucket=min(len(natural_language_query) // 50 * 50, 500),
        )

        engine_result = self.engine.query(
            natural_language_query,
            dry_run=False,
            cancellation_token=cancellation_token,
            event_callback=event_callback,
            context=context,
        )
        if not engine_result.success:
            raise RuntimeError(f"Query failed: {engine_result.error}")

        result = QueryResult(
            results=engine_result.rows,
            query=engine_result.sql,
            parameters=engine_result.parameters,
            natural_language_query=natural_language_query,
        )
        return result.dataframe

    def query_arrow(
        self,
        natural_language_query: str,
        cancellation_token: Optional[Any] = None,
        context: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """
        Convert a natural language question directly into an Apache PyArrow Table.

        Zero-copy data exchange format ideal for ML pipelines, Parquet serialization,
        and distributed computing.
        """
        result = self.query_advanced(
            natural_language_query,
            cancellation_token=cancellation_token,
            context=context,
            **kwargs,
        )
        return result.arrow

    def query_polars(
        self,
        natural_language_query: str,
        cancellation_token: Optional[Any] = None,
        context: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """
        Convert a natural language question directly into a Polars DataFrame.

        High-performance multi-threaded DataFrame format ideal for modern data engineering.
        """
        result = self.query_advanced(
            natural_language_query,
            cancellation_token=cancellation_token,
            context=context,
            **kwargs,
        )
        return result.polars

    def query_advanced(
        self,
        natural_language_query: str,
        schema: Optional[str] = None,
        schema_file: Optional[Union[str, Path]] = None,
        cancellation_token: Optional[Any] = None,
        event_callback: Optional[Callable[[Any], None]] = None,
        context: Optional[str] = None,
    ) -> QueryResult:
        """
        Full pipeline returning the rich ``QueryResult`` object.
        """
        engine_result = self.engine.query(
            natural_language_query,
            dry_run=False,
            cancellation_token=cancellation_token,
            event_callback=event_callback,
            context=context,
        )
        if not engine_result.success:
            raise RuntimeError(f"Query failed: {engine_result.error}")

        return QueryResult(
            results=engine_result.rows,
            query=engine_result.sql,
            parameters=engine_result.parameters,
            natural_language_query=natural_language_query,
        )

    def stream_query(
        self,
        natural_language_query: str,
        cancellation_token: Optional[Any] = None,
        context: Optional[str] = None,
    ) -> Iterator["QueryEvent"]:
        """
        Execute a query while synchronously streaming fine-grained QueryEvent instances.

        Enables client applications and streaming services to report live
        state transitions (planning, SQL synthesis, validation, execution).
        """
        import queue
        import threading
        from teshq.events import EventType, QueryEvent

        event_queue: queue.Queue[Optional[QueryEvent]] = queue.Queue()

        def _on_event(evt: QueryEvent) -> None:
            event_queue.put(evt)

        def _worker() -> None:
            try:
                self.engine.query(
                    natural_language_query,
                    dry_run=False,
                    cancellation_token=cancellation_token,
                    event_callback=_on_event,
                    context=context,
                )
            except Exception as exc:
                event_queue.put(QueryEvent(event_type=EventType.ERROR, stage="error", message=str(exc)))
            finally:
                event_queue.put(None)

        worker_thread = threading.Thread(target=_worker, daemon=True)
        worker_thread.start()

        while True:
            evt = event_queue.get()
            if evt is None:
                break
            yield evt

    async def astream_query(
        self,
        natural_language_query: str,
        cancellation_token: Optional[Any] = None,
        context: Optional[str] = None,
    ) -> AsyncIterator["QueryEvent"]:
        """
        Execute a query while asynchronously streaming fine-grained QueryEvent instances.

        Enables asynchronous event consumers and streaming services to process live progress.
        """
        import asyncio
        from teshq.events import EventType, QueryEvent

        event_queue: asyncio.Queue[Optional[QueryEvent]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def _on_event(evt: QueryEvent) -> None:
            loop.call_soon_threadsafe(event_queue.put_nowait, evt)

        def _worker() -> None:
            try:
                self.engine.query(
                    natural_language_query,
                    dry_run=False,
                    cancellation_token=cancellation_token,
                    event_callback=_on_event,
                    context=context,
                )
            except Exception as exc:
                _on_event(QueryEvent(event_type=EventType.ERROR, stage="error", message=str(exc)))
            finally:
                loop.call_soon_threadsafe(event_queue.put_nowait, None)

        loop.run_in_executor(None, _worker)

        while True:
            evt = await event_queue.get()
            if evt is None:
                break
            yield evt

    def create_session(self, session_id: Optional[str] = None) -> "TeshChatSession":
        """
        Create a new stateful multi-turn conversational session.
        """
        from teshq.session import TeshChatSession
        return TeshChatSession(client=self, session_id=session_id)

    def get_schema_tree(self) -> Dict[str, Any]:
        """
        Get a structured hierarchical schema tree of database tables and columns.

        Returns:
            A dictionary containing database name and a list of tables with column metadata.
        """
        schema_info = self.introspect_database()
        db_name = "database"
        if self.db_url:
            db_name = self.db_url.split("/")[-1].split("?")[0] or "database"

        tables_data = []
        for table_name, table_meta in schema_info.get("tables", {}).items():
            cols = []
            for col in table_meta.get("columns", []):
                cols.append({
                    "name": col.get("name"),
                    "type": str(col.get("type", "TEXT")),
                    "is_pk": bool(col.get("primary_key", False)),
                    "is_fk": bool(col.get("foreign_key", False)),
                    "nullable": bool(col.get("nullable", True)),
                })
            tables_data.append({
                "name": table_name,
                "columns": cols,
                "row_count": table_meta.get("row_count"),
            })

        return {
            "database": db_name,
            "dialect": str(getattr(self.engine, "_dialect", "generic")),
            "tables": tables_data,
        }


    def health_check(self) -> Dict[str, Any]:
        """Run system health checks. Returns a health report dict."""
        track_feature("TeshQuery.health_check")
        return HealthChecker().run_all_checks()

    # ------------------------------------------------------------------
    # Async API
    # ------------------------------------------------------------------

    async def aquery(
        self,
        natural_language_query: str,
        output_format: str = "dataframe",
        return_sql: bool = False,
        cancellation_token: Optional[Any] = None,
        event_callback: Optional[Callable[[Any], None]] = None,
        context: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """Async counterpart of :meth:`query`.

        Runs the full NL → SQL → execute pipeline without blocking the
        event loop (delegates to a thread-pool executor internally).

        Args:
            natural_language_query: Question in plain English.
            output_format: "dataframe" (default), "dict", "arrow", "polars", "csv", or "excel".
            return_sql: If True, include SQL in the response.
            cancellation_token: Optional CancellationToken to abort query execution.
            event_callback: Optional callback receiving QueryEvent instances.
            context: Optional domain or business context string.

        Returns:
            - ``pd.DataFrame`` when ``output_format="dataframe"``.
            - ``List[Dict]`` when ``output_format="dict"``.
            - ``pyarrow.Table`` when ``output_format="arrow"``.
            - ``polars.DataFrame`` when ``output_format="polars"``.
            - CSV string or saved file path when ``output_format="csv"``.
            - Saved file path when ``output_format="excel"``.
        """
        import asyncio

        loop = asyncio.get_running_loop()
        query_kwargs = {
            "output_format": output_format,
            "return_sql": return_sql,
            **kwargs,
        }
        if cancellation_token is not None:
            query_kwargs["cancellation_token"] = cancellation_token
        if event_callback is not None:
            query_kwargs["event_callback"] = event_callback
        if context is not None:
            query_kwargs["context"] = context

        return await loop.run_in_executor(
            None,
            lambda: self.query(natural_language_query, **query_kwargs),
        )


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------

def introspect(db_url: str, **kwargs) -> Dict[str, Any]:
    """
    Quick database introspection without LLM — no API key required.
    """
    track_feature("teshq.api.introspect")
    schema_info = introspect_db(db_url=db_url, **kwargs)
    return schema_info


def query(
    natural_language_query: str,
    db_url: str,
    output_format: str = "dataframe",
    output_path: Optional[str] = None,
    gemini_api_key: Optional[str] = None,
    provider: Optional[str] = None,
    azure_api_key: Optional[str] = None,
    azure_endpoint: Optional[str] = None,
    azure_deployment: Optional[str] = None,
    **kwargs,
) -> Any:
    """Quick query execution convenience function."""
    track_feature("teshq.api.query", query_length_bucket=min(len(natural_language_query) // 50 * 50, 500))
    client = TeshQuery(
        db_url=db_url,
        gemini_api_key=gemini_api_key,
        provider=provider,
        azure_api_key=azure_api_key,
        azure_endpoint=azure_endpoint,
        azure_deployment=azure_deployment,
    )
    return client.query(natural_language_query, output_format=output_format, output_path=output_path, **kwargs)


def health_check() -> Dict[str, Any]:
    """Quick health check — no credentials required."""
    track_feature("teshq.api.health_check")
    return HealthChecker().run_all_checks()
