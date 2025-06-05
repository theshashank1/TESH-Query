from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from utils.keys import get_db_url


def execute_sql_query(
    db_url: Optional[str], query: str, parameters: Optional[Dict[str, Any]] = None, api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Executes a SQL query against the configured database, optionally using provided parameters.

    Args:
        db_url: The database connection URL. If None, attempts to get it from configuration.
        query (str): SQL query with named parameters like `:param`.
        parameters (dict): Dictionary of parameters to safely bind.
    Returns:
        A list of dictionaries, where each dictionary represents a row from the query result.
    """

    engine = create_engine(get_db_url())
    parameters = parameters or {}

    try:
        with engine.connect() as conn:
            result = conn.execute(text(query), parameters)
            return [dict(row._mapping) for row in result]
    except SQLAlchemyError as e:
        print(f"[SQL ERROR] {e}")
        return []


if __name__ == "__main__":
    # Replace with your actual database URL for testing
    query = "SELECT 1"
    parameters = {}
    result = execute_sql_query(query, parameters)
    print(result)
