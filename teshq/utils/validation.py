"""Input validation utilities for TESH-Query."""

import re
import os
from typing import Any, Optional, Union, List, Dict
from urllib.parse import urlparse
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


def validate_database_url(url: str) -> str:
    """
    Validate database URL format and connectivity.
    
    Args:
        url: Database URL string
        
    Returns:
        Validated URL string
        
    Raises:
        ValidationError: If URL is invalid or unreachable
    """
    if not url or not isinstance(url, str):
        raise ValidationError("Database URL must be a non-empty string")
    
    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise ValidationError(f"Invalid URL format: {e}")
    
    # Check scheme
    supported_schemes = ['postgresql', 'mysql', 'sqlite', 'postgresql+psycopg2', 'mysql+pymysql']
    if parsed.scheme not in supported_schemes:
        raise ValidationError(
            f"Unsupported database scheme '{parsed.scheme}'. "
            f"Supported schemes: {', '.join(supported_schemes)}"
        )
    
    # Validate SQLAlchemy URL format
    try:
        # Test URL parsing with SQLAlchemy
        sqlalchemy.engine.url.make_url(url)
    except Exception as e:
        raise ValidationError(f"Invalid SQLAlchemy URL format: {e}")
    
    return url


def test_database_connection(url: str) -> bool:
    """
    Test database connection without raising exceptions.
    
    Args:
        url: Database URL string
        
    Returns:
        True if connection successful, False otherwise
    """
    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            # Simple test query
            conn.execute(sqlalchemy.text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False
    except Exception:
        return False


def validate_gemini_api_key(api_key: str) -> str:
    """
    Validate Gemini API key format.
    
    Args:
        api_key: API key string
        
    Returns:
        Validated API key
        
    Raises:
        ValidationError: If API key is invalid
    """
    if not api_key or not isinstance(api_key, str):
        raise ValidationError("API key must be a non-empty string")
    
    # Basic format validation (typical Google API key format)
    if not re.match(r'^[A-Za-z0-9_-]{35,45}$', api_key.strip()):
        raise ValidationError(
            "API key format appears invalid. Expected 35-45 alphanumeric characters with underscores/dashes."
        )
    
    return api_key.strip()


def validate_file_path(path: str, check_parent_exists: bool = True) -> str:
    """
    Validate file path.
    
    Args:
        path: File path string
        check_parent_exists: Whether to check if parent directory exists
        
    Returns:
        Validated absolute path
        
    Raises:
        ValidationError: If path is invalid
    """
    if not path or not isinstance(path, str):
        raise ValidationError("File path must be a non-empty string")
    
    # Convert to absolute path
    abs_path = os.path.abspath(path.strip())
    
    # Check parent directory exists if requested
    if check_parent_exists:
        parent_dir = os.path.dirname(abs_path)
        if not os.path.exists(parent_dir):
            raise ValidationError(f"Parent directory does not exist: {parent_dir}")
        
        if not os.access(parent_dir, os.W_OK):
            raise ValidationError(f"Parent directory is not writable: {parent_dir}")
    
    return abs_path


def validate_query_parameters(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate SQL query parameters.
    
    Args:
        params: Dictionary of query parameters
        
    Returns:
        Validated parameters
        
    Raises:
        ValidationError: If parameters are invalid
    """
    if params is None:
        return {}
    
    if not isinstance(params, dict):
        raise ValidationError("Query parameters must be a dictionary")
    
    # Check for SQL injection patterns in parameter names
    dangerous_patterns = [';', '--', '/*', '*/', 'DROP', 'DELETE', 'UPDATE', 'INSERT']
    
    validated = {}
    for key, value in params.items():
        if not isinstance(key, str):
            raise ValidationError(f"Parameter key must be string, got {type(key)}")
        
        # Check for suspicious patterns in key names
        if any(pattern.lower() in key.lower() for pattern in dangerous_patterns):
            raise ValidationError(f"Parameter name contains suspicious pattern: {key}")
        
        # Validate parameter name format (alphanumeric + underscore)
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', key):
            raise ValidationError(f"Invalid parameter name format: {key}")
        
        # Basic value validation
        if isinstance(value, (str, int, float, bool)) or value is None:
            validated[key] = value
        else:
            raise ValidationError(f"Parameter value type not supported: {type(value)}")
    
    return validated


def validate_sql_query(query: str) -> str:
    """
    Basic SQL query validation.
    
    Args:
        query: SQL query string
        
    Returns:
        Validated query string
        
    Raises:
        ValidationError: If query is invalid or dangerous
    """
    if not query or not isinstance(query, str):
        raise ValidationError("SQL query must be a non-empty string")
    
    query = query.strip()
    
    # Check for dangerous SQL patterns
    dangerous_patterns = [
        r'\bDROP\s+TABLE\b',
        r'\bDROP\s+DATABASE\b',
        r'\bDELETE\s+FROM\b.*\bWHERE\s+1\s*=\s*1\b',
        r'\bTRUNCATE\b',
        r'\bALTER\s+TABLE\b',
        r';\s*DROP\b',
        r'--',
        r'/\*.*\*/',
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, query, re.IGNORECASE):
            raise ValidationError(f"Query contains potentially dangerous pattern: {pattern}")
    
    # Must be a SELECT statement for safety
    if not re.match(r'^\s*SELECT\b', query, re.IGNORECASE):
        raise ValidationError("Only SELECT queries are allowed")
    
    return query


def validate_model_name(model_name: str) -> str:
    """
    Validate Gemini model name.
    
    Args:
        model_name: Model name string
        
    Returns:
        Validated model name
        
    Raises:
        ValidationError: If model name is invalid
    """
    if not model_name or not isinstance(model_name, str):
        raise ValidationError("Model name must be a non-empty string")
    
    model_name = model_name.strip()
    
    # List of known valid Gemini models
    valid_models = [
        'gemini-1.5-flash',
        'gemini-1.5-flash-latest',
        'gemini-1.5-pro',
        'gemini-1.5-pro-latest',
        'gemini-2.0-flash-lite',
        'gemini-pro',
        'gemini-pro-vision'
    ]
    
    if model_name not in valid_models:
        raise ValidationError(
            f"Unknown model name '{model_name}'. "
            f"Supported models: {', '.join(valid_models)}"
        )
    
    return model_name


def validate_config_data(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate complete configuration data.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Validated configuration
        
    Raises:
        ValidationError: If configuration is invalid
    """
    if not isinstance(config, dict):
        raise ValidationError("Configuration must be a dictionary")
    
    validated = {}
    
    # Validate DATABASE_URL if present
    if 'DATABASE_URL' in config and config['DATABASE_URL']:
        validated['DATABASE_URL'] = validate_database_url(config['DATABASE_URL'])
    
    # Validate GEMINI_API_KEY if present
    if 'GEMINI_API_KEY' in config and config['GEMINI_API_KEY']:
        validated['GEMINI_API_KEY'] = validate_gemini_api_key(config['GEMINI_API_KEY'])
    
    # Validate GEMINI_MODEL_NAME if present
    if 'GEMINI_MODEL_NAME' in config and config['GEMINI_MODEL_NAME']:
        validated['GEMINI_MODEL_NAME'] = validate_model_name(config['GEMINI_MODEL_NAME'])
    
    # Validate file paths
    for path_key in ['OUTPUT_PATH', 'FILE_STORE_PATH']:
        if path_key in config and config[path_key]:
            validated[path_key] = validate_file_path(config[path_key], check_parent_exists=False)
    
    return validated


# CLI argument validators
def validate_cli_integer(value: str, min_val: Optional[int] = None, max_val: Optional[int] = None) -> int:
    """
    Validate CLI integer argument.
    
    Args:
        value: String value from CLI
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        
    Returns:
        Validated integer
        
    Raises:
        ValidationError: If value is invalid
    """
    try:
        int_val = int(value)
    except ValueError:
        raise ValidationError(f"Invalid integer value: {value}")
    
    if min_val is not None and int_val < min_val:
        raise ValidationError(f"Value must be >= {min_val}, got {int_val}")
    
    if max_val is not None and int_val > max_val:
        raise ValidationError(f"Value must be <= {max_val}, got {int_val}")
    
    return int_val


def validate_cli_choice(value: str, choices: List[str]) -> str:
    """
    Validate CLI choice argument.
    
    Args:
        value: String value from CLI
        choices: List of valid choices
        
    Returns:
        Validated choice
        
    Raises:
        ValidationError: If choice is invalid
    """
    if value not in choices:
        raise ValidationError(f"Invalid choice '{value}'. Valid choices: {', '.join(choices)}")
    
    return value