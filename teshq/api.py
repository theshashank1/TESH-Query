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
    sql_info = client.generate_sql("count all active users")
    print(sql_info['query'])
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .config.paths import SCHEMA_DIR
from .core.engine import TeshEngine
from .core.introspect import introspect_db, save_schema_to_files
from .utils.config import get_config, save_config
from .utils.connection import connection_manager
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

        # Resolve database URL
        self.db_url = db_url or config.get("DATABASE_URL") or None

        # Resolve provider
        self._provider = (
            provider
            or config.get("LLM_PROVIDER")
            or ("azure" if azure_api_key else "google")
        )

        # Resolve Google credentials
        self.gemini_api_key = gemini_api_key or config.get("GEMINI_API_KEY") or None
        self.gemini_model = gemini_model or config.get("GEMINI_MODEL") or "gemini-2.0-flash-lite"

        # Resolve Azure credentials
        self.azure_api_key = azure_api_key or config.get("AZURE_OPENAI_API_KEY") or None
        self.azure_endpoint = azure_endpoint or config.get("AZURE_OPENAI_ENDPOINT") or None
        self.azure_deployment = azure_deployment or config.get("AZURE_OPENAI_DEPLOYMENT") or None
        self.azure_api_version = azure_api_version or config.get("AZURE_OPENAI_API_VERSION") or "2024-02-01"

        self.auto_save_config = auto_save_config

        # Validate required config
        if not self.db_url:
            raise ValueError(
                "Database URL is required. Provide it via db_url= or configure with: teshq config --db"
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
            if self._provider == "azure":
                self._engine = TeshEngine(
                    db_url=self.db_url,
                    provider="azure",
                    api_key=self.azure_api_key,
                    model_name=self.azure_deployment,
                    azure_endpoint=self.azure_endpoint,
                    azure_deployment=self.azure_deployment,
                    azure_api_version=self.azure_api_version,
                )
            else:
                self._engine = TeshEngine(
                    db_url=self.db_url,
                    provider="google",
                    api_key=self.gemini_api_key,
                    model_name=self.gemini_model,
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
        schema: Optional[str] = None,
        schema_file: Optional[Union[str, Path]] = None,
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
        schema: Optional[str] = None,
        schema_file: Optional[Union[str, Path]] = None,
        return_sql: bool = False,
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Full pipeline: generate SQL from natural language then execute it.

        Args:
            natural_language_query: Question in plain English.
            return_sql: If True, return a dict with 'sql', 'parameters', and 'results'.
                        If False (default), return the results list directly.

        Returns:
            List of result dicts, or a dict with sql+results when return_sql=True.
        """
        track_feature(
            "TeshQuery.query",
            query_length_bucket=min(len(natural_language_query) // 50 * 50, 500),
            return_sql=return_sql,
        )

        engine_result = self.engine.query(natural_language_query, dry_run=False)
        if not engine_result.success:
            raise RuntimeError(f"Query failed: {engine_result.error}")

        result = QueryResult(
            results=engine_result.rows,
            query=engine_result.sql,
            parameters=engine_result.parameters,
            natural_language_query=natural_language_query,
        )

        if return_sql:
            return result.to_dict(include_sql=True)
        return result.results

    def query_advanced(
        self,
        natural_language_query: str,
        schema: Optional[str] = None,
        schema_file: Optional[Union[str, Path]] = None,
    ) -> QueryResult:
        """
        Full pipeline returning the rich QueryResult object (includes .dataframe, .to_dict(), etc.).
        """
        engine_result = self.engine.query(natural_language_query, dry_run=False)
        if not engine_result.success:
            raise RuntimeError(f"Query failed: {engine_result.error}")

        return QueryResult(
            results=engine_result.rows,
            query=engine_result.sql,
            parameters=engine_result.parameters,
            natural_language_query=natural_language_query,
        )

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
        return_sql: bool = False,
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """Async counterpart of :meth:`query`.

        Runs the full NL → SQL → execute pipeline without blocking the
        event loop (delegates to a thread-pool executor internally).

        Args:
            natural_language_query: Question in plain English.
            return_sql: If True, include SQL in the returned dict.

        Returns:
            List of result dicts, or a dict with sql+results when *return_sql* is True.
        """
        import asyncio

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.query(natural_language_query, return_sql=return_sql),
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
    gemini_api_key: Optional[str] = None,
    provider: Optional[str] = None,
    azure_api_key: Optional[str] = None,
    azure_endpoint: Optional[str] = None,
    azure_deployment: Optional[str] = None,
    **kwargs,
) -> List[Dict[str, Any]]:
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
    return client.query(natural_language_query, **kwargs)


def health_check() -> Dict[str, Any]:
    """Quick health check — no credentials required."""
    track_feature("teshq.api.health_check")
    return HealthChecker().run_all_checks()
