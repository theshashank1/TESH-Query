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
from .utils.config import get_config, save_config
from .utils.output import QueryResult


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
            gemini_model: Gemini model name. Defaults to 'gemini-2.0-flash-lite'.
            auto_save_config: Whether to automatically save configuration.
        """
        self.db_url = db_url
        self.gemini_api_key = gemini_api_key
        self.gemini_model = gemini_model or "gemini-2.0-flash-lite"
        self.auto_save_config = auto_save_config

        # Try to get configuration if not provided
        if not self.db_url or not self.gemini_api_key:
            config = get_config()
            self.db_url = self.db_url or config.get("DATABASE_URL")
            self.gemini_api_key = self.gemini_api_key or config.get("GEMINI_API_KEY")
            self.gemini_model = self.gemini_model or config.get("GEMINI_MODEL_NAME", "gemini-2.0-flash-lite")

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

        Args:
            detect_relationships: Whether to detect implicit relationships.
            include_indexes: Whether to include index information.
            include_sample_data: Whether to include sample data.
            sample_size: Number of sample rows to include.
            save_to_files: Whether to save schema to files.
            output_dir: Directory to save files (if save_to_files=True).

        Returns:
            Dict containing the complete schema information.
        """
        schema_info = introspect_db(
            db_url=self.db_url,
            detect_relationships=detect_relationships,
            include_indexes=include_indexes,
            include_sample_data=include_sample_data,
            sample_size=sample_size,
        )

        # Cache the schema for later use
        self._schema_cache = schema_info

        # Save to files if requested
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

        Args:
            schema_path: Path to the schema text file.

        Returns:
            str: Schema content as text.
        """
        return self.llm_generator.load_schema(str(schema_path))

    def generate_sql(
        self, natural_language_query: str, schema: Optional[str] = None, schema_file: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        """
        Generate SQL from a natural language query.

        Args:
            natural_language_query: The natural language query.
            schema: Schema text. If None, will try to use cached schema or load from file.
            schema_file: Path to schema file. Used if schema is None.

        Returns:
            Dict containing 'query' and 'parameters' keys.
        """
        # Determine schema to use
        if schema is None:
            if schema_file:
                schema = self.load_schema_from_file(schema_file)
            elif self._schema_cache:
                # Use cached schema - convert to text format
                schema = self._format_schema_for_llm(self._schema_cache)
            else:
                # Try to load from default location
                default_schema_path = Path("db_schema/schema.txt")
                if default_schema_path.exists():
                    schema = self.load_schema_from_file(default_schema_path)
                else:
                    raise ValueError(
                        "No schema provided. Either:\n"
                        "1. Pass schema text directly\n"
                        "2. Pass schema_file path\n"
                        "3. Run introspect_database() first\n"
                        "4. Ensure db_schema/schema.txt exists"
                    )

        return self.llm_generator.generate_sql(natural_language_query, schema)

    def execute_query(self, sql_query: str, parameters: Optional[Dict[str, Any]] = None) -> QueryResult:
        """
        Execute a SQL query against the database.

        Args:
            sql_query: The SQL query to execute.
            parameters: Optional parameters for the query.

        Returns:
            QueryResult object with normalized, consistent results.
        """
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

        Args:
            natural_language_query: The natural language query.
            schema: Schema text. If None, will try to use cached schema or load from file.
            schema_file: Path to schema file. Used if schema is None.
            return_sql: If True, returns dict with 'sql', 'parameters', and 'results'.

        Returns:
            Query results as list of dicts, complete info dict if return_sql=True,
            or QueryResult object for advanced use cases.
        """
        # Generate SQL
        sql_info = self.generate_sql(natural_language_query, schema, schema_file)
        sql_query = sql_info["query"]
        parameters = sql_info["parameters"]

        # Execute query and get QueryResult object
        raw_results = execute_sql_query(db_url=self.db_url, query=sql_query, parameters=parameters)
        result = QueryResult(raw_results, sql_query, parameters, natural_language_query)

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

        Args:
            natural_language_query: The natural language query.
            schema: Schema text. If None, will try to use cached schema or load from file.
            schema_file: Path to schema file. Used if schema is None.

        Returns:
            QueryResult object with normalized data, DataFrame access, and display methods.
        """
        # Generate SQL
        sql_info = self.generate_sql(natural_language_query, schema, schema_file)
        sql_query = sql_info["query"]
        parameters = sql_info["parameters"]

        # Execute query and get QueryResult object
        raw_results = execute_sql_query(db_url=self.db_url, query=sql_query, parameters=parameters)
        return QueryResult(raw_results, sql_query, parameters, natural_language_query)

    def _format_schema_for_llm(self, schema_info: Dict[str, Any]) -> str:
        """
        Convert schema info dict to text format suitable for LLM.

        Args:
            schema_info: Schema information dictionary from introspection.

        Returns:
            str: Formatted schema text.
        """
        if "data_model_summary" in schema_info:
            return schema_info["data_model_summary"]

        # Fallback: create basic schema text from tables
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


# Convenience functions for quick usage
def introspect(db_url: str, **kwargs) -> Dict[str, Any]:
    """
    Quick database introspection.

    Args:
        db_url: Database connection URL.
        **kwargs: Additional arguments for introspect_database().

    Returns:
        Schema information dictionary.
    """
    client = TeshQuery(db_url=db_url, gemini_api_key="dummy")  # API key not needed for introspection
    return client.introspect_database(**kwargs)


def query(
    natural_language_query: str, db_url: str, gemini_api_key: str, schema: Optional[str] = None, **kwargs
) -> List[Dict[str, Any]]:
    """
    Quick query execution.

    Args:
        natural_language_query: The natural language query.
        db_url: Database connection URL.
        gemini_api_key: Gemini API key.
        schema: Optional schema text.
        **kwargs: Additional arguments for query().

    Returns:
        Query results.
    """
    client = TeshQuery(db_url=db_url, gemini_api_key=gemini_api_key)
    return client.query(natural_language_query, schema=schema, **kwargs)
