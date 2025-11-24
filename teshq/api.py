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

from .core.db import connect_database, disconnect_database
from .core.introspect import introspect_db, save_schema_to_files
from .core.llm import SQLQueryGenerator
from .core.query import execute_sql_query
from .utils.analytics import track_feature_usage  # Correctly import the tracking function
from .utils.config import get_config, save_config
from .utils.health import HealthChecker


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
        self.gemini_model = gemini_model or "gemini-1.5-flash"
        self.auto_save_config = auto_save_config

        # Try to get configuration if not provided
        if not self.db_url or not self.gemini_api_key:
            config = get_config()
            self.db_url = self.db_url or config.get("DATABASE_URL")
            self.gemini_api_key = self.gemini_api_key or config.get("GEMINI_API_KEY")
            self.gemini_model = self.gemini_model or config.get("GEMINI_MODEL_NAME", "gemini-1.5-flash")

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
        self._llm_generator = None
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
    def llm_generator(self) -> SQLQueryGenerator:
        """Get or create the LLM generator instance."""
        if self._llm_generator is None:
            self._llm_generator = SQLQueryGenerator(api_key=self.gemini_api_key, model_name=self.gemini_model)
        return self._llm_generator

    def test_connection(self) -> bool:
        """
        Test the database connection.

        Returns:
            bool: True if connection is successful.
        """
        try:
            engine = connect_database(self.db_url)
            if engine:
                disconnect_database(engine)
                return True
            return False
        except Exception:
            return False

    def introspect_database(
        self,
        detect_relationships: bool = True,
        include_indexes: bool = True,
        include_sample_data: bool = False,
        sample_size: int = 3,
        save_to_files: bool = False,
        output_dir: str = ".",
    ) -> Dict[str, Any]:
        """
        Introspect the database schema.
        """
        # Track this high-level feature call
        track_feature_usage(
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
            save_schema_to_files(
                schema_info,
                output_dir=output_dir,
                json_filename="schema.json",
                text_filename="schema.txt",
            )

        return schema_info

    def load_schema_from_file(self, schema_path: Union[str, Path]) -> str:
        """
        Load schema from a text file.
        """
        return self.llm_generator.load_schema(str(schema_path))

    def generate_sql(
        self, natural_language_query: str, schema: Optional[str] = None, schema_file: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        """
        Generate SQL from a natural language query.
        """
        current_schema = schema
        if current_schema is None:
            if schema_file:
                current_schema = self.load_schema_from_file(schema_file)
            elif self._schema_cache:
                current_schema = self._format_schema_for_llm(self._schema_cache)
            else:
                default_schema_path = Path("db_schema/schema.txt")
                if default_schema_path.exists():
                    current_schema = self.load_schema_from_file(default_schema_path)
                else:
                    raise ValueError("No schema provided. Please run introspect_database() first or provide a schema.")

        return self.llm_generator.generate_sql(natural_language_query, current_schema)

    def execute_query(self, sql_query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute a SQL query against the database.
        """
        return execute_sql_query(db_url=self.db_url, query=sql_query, parameters=parameters or {})

    def query(
        self,
        natural_language_query: str,
        schema: Optional[str] = None,
        schema_file: Optional[Union[str, Path]] = None,
        return_sql: bool = False,
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Complete workflow: generate SQL from natural language and execute it.
        """
        # Track this primary user-facing feature
        track_feature_usage(
            "TeshQuery.query", properties={"query_length": len(natural_language_query), "return_sql": return_sql}
        )

        sql_info = self.generate_sql(natural_language_query, schema, schema_file)
        sql_query = sql_info["query"]
        parameters = sql_info["parameters"]

        results = self.execute_query(sql_query, parameters)

        if return_sql:
            return {
                "sql": sql_query,
                "parameters": parameters,
                "results": results,
                "natural_language_query": natural_language_query,
            }
        else:
            return results

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
        track_feature_usage("TeshQuery.health_check")

        health_checker = HealthChecker()
        return health_checker.run_all_checks()


# Convenience functions for quick usage
def introspect(db_url: str, **kwargs) -> Dict[str, Any]:
    """
    Quick database introspection.
    """
    # Track the usage of this convenience function
    track_feature_usage("teshq.api.introspect", properties=kwargs)
    client = TeshQuery(db_url=db_url, gemini_api_key="dummy")  # API key not needed
    return client.introspect_database(**kwargs)


def query(
    natural_language_query: str, db_url: str, gemini_api_key: str, schema: Optional[str] = None, **kwargs
) -> List[Dict[str, Any]]:
    """
    Quick query execution.
    """
    # Track the usage of this convenience function
    track_feature_usage("teshq.api.query", {"query_length": len(natural_language_query)})
    client = TeshQuery(db_url=db_url, gemini_api_key=gemini_api_key)
    return client.query(natural_language_query, schema=schema, **kwargs)


def health_check() -> Dict[str, Any]:
    """
    Quick health check execution.

    Returns:
        Dict[str, Any]: Health check report with status, checks, and summary.
    """
    # Track the usage of this convenience function
    track_feature_usage("teshq.api.health_check")
    health_checker = HealthChecker()
    return health_checker.run_all_checks()
