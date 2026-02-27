"""
TESH-Query Programmatic API

This module provides a clean, easy-to-use interface for programmatic access to
TESH-Query functionality without needing to use the CLI.

Example usage:
    import teshq

    # Initialize the client
    client = teshq.TeshQuery(
        db_url="postgresql://user:pass@host:port/dbname",
        gemini_api_key="your-api-key"
    )

    # Introspect database schema
    schema = client.introspect_database()

    # Execute natural language queries
    result = client.query("show me all users who registered last month")

    # Generate SQL without executing
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

    This class provides a clean API for database introspection, SQL generation,
    and query execution using natural language.
    """

    def __init__(
        self,
        db_url: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        gemini_model: Optional[str] = None,
        auto_save_config: bool = False,
    ):
        """
        Initialize the TeshQuery client.

        Args:
            db_url: Database connection URL. If None, will try to get from config.
            gemini_api_key: Google Gemini API key. If None, will try to get from config.
            gemini_model: Gemini model name. Defaults to 'gemini-1.5-flash'.
            auto_save_config: Whether to automatically save configuration.
        """
        self.db_url = db_url
        self.gemini_api_key = gemini_api_key
        self.gemini_model = gemini_model  # May be None; resolved below after config lookup
        self.auto_save_config = auto_save_config

        # Try to get configuration if not provided
        if not self.db_url or not self.gemini_api_key or not self.gemini_model:
            config = get_config()
            self.db_url = self.db_url or config.get("DATABASE_URL")
            self.gemini_api_key = self.gemini_api_key or config.get("GEMINI_API_KEY")
            # Prefer arg → config → fallback default
            self.gemini_model = self.gemini_model or config.get("GEMINI_MODEL_NAME") or "gemini-1.5-flash"

        # Validate required parameters
        if not self.db_url:
            raise ValueError(
                "Database URL is required. Provide it via db_url parameter or "
                "configure it using the CLI: 'teshq config --db'"
            )

        if not self.gemini_api_key:
            raise ValueError(
                "Gemini API key is required. Provide it via gemini_api_key parameter or "
                "configure it using the CLI: 'teshq config --gemini'"
            )

        # Initialize components
        self._engine = None
        self._schema_cache = None

        # Auto-save configuration if requested
        if self.auto_save_config:
            self.save_configuration()

    def save_configuration(self) -> bool:
        """
        Save the current configuration to the config file.

        Returns:
            bool: True if configuration was saved successfully.
        """
        config_data = {
            "DATABASE_URL": self.db_url,
            "GEMINI_API_KEY": self.gemini_api_key,
            "GEMINI_MODEL_NAME": self.gemini_model,
        }
        return save_config(config_data)

    @property
    def engine(self) -> TeshEngine:
        """Get or create the TeshEngine instance."""
        if self._engine is None:
            self._engine = TeshEngine(
                db_url=self.db_url,
                api_key=self.gemini_api_key,
                model_name=self.gemini_model,
            )
        return self._engine

    def test_connection(self) -> bool:
        """
        Test the database connection.

        Returns:
            bool: True if connection is successful.
        """
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
        Introspects the configured database and returns a structured representation of its schema.

        Parameters:
        	detect_relationships (bool): Detect implicit foreign-key relationships between tables.
        	include_indexes (bool): Include index metadata for tables.
        	include_sample_data (bool): Include sample rows for tables.
        	sample_size (int): Number of sample rows to include per table when sample data is requested.
        	save_to_files (bool): If True, persist the schema to files.
        	output_dir (Optional[str]): Directory to write schema files when saving; defaults to the user's schema cache directory (~/.teshq/schema/).

        Returns:
        	schema_info (Dict[str, Any]): A dictionary containing the complete introspected schema information.
        """
        # Track this high-level feature call
        track_feature(
            "TeshQuery.introspect_database",
            properties={
                "detect_relationships": detect_relationships,
                "include_indexes": include_indexes,
                "include_sample_data": include_sample_data,
                "sample_size": sample_size,
                "save_to_files": save_to_files,
            },
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
        self, natural_language_query: str, schema: Optional[str] = None, schema_file: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        """
        Generate a SQL statement and its parameters from a natural language query using the configured LLM.

        Parameters:
            natural_language_query (str): Natural language description of the desired query.
            schema (Optional[str]): Deprecated in v2. TeshEngine introspects the database automatically.
            schema_file (Optional[Union[str, Path]]): Deprecated in v2.

        Returns:
            Dict[str, Any]: A dictionary with keys 'query' (the generated SQL string) and 'parameters' (the parameters for the query).
        """
        result = self.engine.query(natural_language_query, dry_run=True)
        if not result.success:
            raise RuntimeError(f"SQL Generation failed: {result.error}")
            
        return {"query": result.sql, "parameters": result.parameters}

    def execute_query(self, sql_query: str, parameters: Optional[Dict[str, Any]] = None) -> QueryResult:
        """
        Execute a SQL query against the database.
        """
        # Execute query and wrap in Output result
        from teshq.core.query import execute_sql_query
        raw_results = execute_sql_query(db_url=self.db_url, query=sql_query, parameters=parameters or {})
        return QueryResult(raw_results, sql_query, parameters)

    def query(
        self,
        natural_language_query: str,
        schema: Optional[str] = None,
        schema_file: Optional[Union[str, Path]] = None,
        return_sql: bool = False,
    ) -> Union[List[Dict[str, Any]], Dict[str, Any], QueryResult]:
        """
        Complete workflow: generate SQL from natural language and execute it.
        """
        track_feature(
            "TeshQuery.query", properties={"query_length": len(natural_language_query), "return_sql": return_sql}
        )

        engine_result = self.engine.query(natural_language_query, dry_run=False)
        if not engine_result.success:
            raise RuntimeError(f"Query failed: {engine_result.error}")

        # Wrap in output formatter
        result = QueryResult(engine_result.rows, engine_result.sql, engine_result.parameters, natural_language_query)

        if return_sql:
            return result.to_dict(include_sql=True)
        else:
            return result.results

    def query_advanced(
        self,
        natural_language_query: str,
        schema: Optional[str] = None,
        schema_file: Optional[Union[str, Path]] = None,
    ) -> QueryResult:
        """
        Advanced query method that returns a QueryResult object with full functionality.
        """
        engine_result = self.engine.query(natural_language_query, dry_run=False)
        if not engine_result.success:
            raise RuntimeError(f"Query failed: {engine_result.error}")

        return QueryResult(engine_result.rows, engine_result.sql, engine_result.parameters, natural_language_query)

    def _format_schema_for_llm(self, schema_info: Dict[str, Any]) -> str:
        """
        Convert schema info dict to text format suitable for LLM.
        """
        if "data_model_summary" in schema_info:
            return schema_info["data_model_summary"]

        schema_text = "Database Schema:\n\n"
        if "tables" in schema_info:
            for table_name, table_info in schema_info["tables"].items():
                schema_text += f"Table: {table_name}\n"
                if "columns" in table_info:
                    for col_name, col_info in table_info["columns"].items():
                        col_type = col_info.get("type", "UNKNOWN")
                        nullable = "NULL" if col_info.get("nullable", True) else "NOT NULL"
                        schema_text += f"  - {col_name}: {col_type} {nullable}\n"
                if "description" in table_info:
                    schema_text += f"  Description: {table_info['description']}\n"
                schema_text += "\n"
        return schema_text

    def health_check(self) -> Dict[str, Any]:
        """
        Run health checks on the system.

        Returns:
            Dict[str, Any]: Health check report with status, checks, and summary.
        """
        # Track this feature usage
        track_feature("TeshQuery.health_check")

        health_checker = HealthChecker()
        return health_checker.run_all_checks()


# Convenience functions for quick usage
def introspect(db_url: str, **kwargs) -> Dict[str, Any]:
    """
    Quick database introspection.
    """
    # Track the usage of this convenience function
    track_feature("teshq.api.introspect", properties=kwargs)
    client = TeshQuery(db_url=db_url, gemini_api_key="dummy")  # API key not needed
    return client.introspect_database(**kwargs)


def query(
    natural_language_query: str, db_url: str, gemini_api_key: str, schema: Optional[str] = None, **kwargs
) -> List[Dict[str, Any]]:
    """
    Quick query execution.
    """
    # Track the usage of this convenience function
    track_feature("teshq.api.query", {"query_length": len(natural_language_query)})
    client = TeshQuery(db_url=db_url, gemini_api_key=gemini_api_key)
    return client.query(natural_language_query, schema=schema, **kwargs)


def health_check() -> Dict[str, Any]:
    """
    Quick health check execution.

    Returns:
        Dict[str, Any]: Health check report with status, checks, and summary.
    """
    # Track the usage of this convenience function
    track_feature("teshq.api.health_check")
    health_checker = HealthChecker()
    return health_checker.run_all_checks()
