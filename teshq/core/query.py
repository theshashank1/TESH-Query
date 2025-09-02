from typing import Any, Dict, List, Optional

from teshq.utils.config import get_database_url as get_db_url
from teshq.utils.connection import execute_query_with_pooling
from teshq.utils.logging import logger, log_query_metrics, log_operation


def execute_sql_query(
    db_url: Optional[str], query: str, parameters: Optional[Dict[str, Any]] = None, api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Executes a SQL query against the configured database using connection pooling and structured logging.

    Args:
        db_url: The database connection URL. If None, attempts to get it from configuration.
        query (str): SQL query with named parameters like `:param`.
        parameters (dict): Dictionary of parameters to safely bind.
        api_key: Optional API key (for backward compatibility).
    Returns:
        A list of dictionaries, where each dictionary represents a row from the query result.
    """
    # Use provided db_url or get from configuration
    connection_url = db_url or get_db_url()
    if not connection_url:
        logger.error("Database URL is required but not provided or configured")
        raise ValueError("Database URL is required. Provide db_url or configure it.")

    parameters = parameters or {}

    try:
        with log_operation("execute_sql_query", query_length=len(query), has_parameters=bool(parameters)):
            # Use the new connection pooling system
            result = execute_query_with_pooling(connection_url, query, parameters)
            
            # Log query metrics
            log_query_metrics(
                query_type="user_query",
                execution_time=0,  # This will be handled by the connection manager
                row_count=len(result),
                query_length=len(query),
                has_parameters=bool(parameters)
            )
            
            logger.success(
                "SQL query executed successfully",
                row_count=len(result),
                query_length=len(query),
                has_parameters=bool(parameters)
            )
            
            return result
            
    except Exception as e:
        logger.error(
            "SQL query execution failed",
            error=e,
            query_length=len(query),
            has_parameters=bool(parameters)
        )
        # Re-raise the exception to maintain existing error handling behavior
        raise


if __name__ == "__main__":
    # Replace with your actual database URL for testing
    query = "SELECT 1"
    parameters = {}
    result = execute_sql_query(None, query, parameters)
    print(result)
