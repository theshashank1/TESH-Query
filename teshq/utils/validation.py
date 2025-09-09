"""
Input validation utilities for TESH-Query

Provides comprehensive validation for configuration, CLI inputs, and API parameters
to ensure production-ready input handling and security.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


class ValidationError(Exception):
    """Custom exception for validation errors."""

    def __init__(self, message: str, field: str = None):
        super().__init__(message)
        self.field = field
        self.message = message


class ConfigValidator:
    """Validates configuration values for production readiness."""

    SUPPORTED_DB_TYPES = {"postgresql", "mysql", "sqlite"}
    GEMINI_API_KEY_PATTERN = re.compile(r"^AIza[0-9A-Za-z-_]{35}$")

    @staticmethod
    def validate_database_url(db_url: str) -> Tuple[bool, str]:
        """Validate database URL format and connection."""
        if not db_url or not isinstance(db_url, str):
            return False, "Database URL cannot be empty"

        try:
            parsed = urlparse(db_url)

            # Check basic URL structure
            if not parsed.scheme:
                return False, "Database URL must include a scheme (postgresql://, mysql://, sqlite://)"

            # Validate supported database types
            if parsed.scheme not in ConfigValidator.SUPPORTED_DB_TYPES:
                return (
                    False,
                    f"Unsupported database type:{parsed.scheme}. Supported: {', '.join(ConfigValidator.SUPPORTED_DB_TYPES)}",
                )

            # Special validation for SQLite
            if parsed.scheme == "sqlite":
                if parsed.path:
                    # Ensure directory exists for SQLite file
                    db_path = Path(parsed.path)
                    try:
                        db_path.parent.mkdir(parents=True, exist_ok=True)
                    except PermissionError:
                        return False, f"Cannot create directory for SQLite database: {db_path.parent}"
                else:
                    return False, "SQLite URL must include a path to the database file"

            # For non-SQLite, validate required components
            else:
                if not parsed.hostname:
                    return False, f"{parsed.scheme} database URL must include hostname"
                if not parsed.path or parsed.path == "/":
                    return False, f"{parsed.scheme} database URL must include database name"

            return True, "Valid database URL format"

        except Exception as e:
            return False, f"Invalid database URL format: {str(e)}"

    @staticmethod
    def validate_database_connection(db_url: str) -> Tuple[bool, str]:
        """Test actual database connection."""
        try:
            # Create engine with connection timeout
            engine = create_engine(
                db_url,
                connect_args=(
                    {
                        "connect_timeout": 10,  # 10 second timeout
                    }
                    if not db_url.startswith("sqlite")
                    else {}
                ),
            )

            # Test connection
            with engine.connect() as conn:
                # Simple test query
                if db_url.startswith("sqlite"):
                    conn.execute(text("SELECT 1"))
                elif db_url.startswith("postgresql"):
                    conn.execute(text("SELECT version()"))
                elif db_url.startswith("mysql"):
                    conn.execute(text("SELECT version()"))

            return True, "Database connection successful"

        except SQLAlchemyError as e:
            return False, f"Database connection failed: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error testing database connection: {str(e)}"

    @staticmethod
    def validate_gemini_api_key(api_key: str) -> Tuple[bool, str]:
        """Validate Gemini API key format."""
        if not api_key or not isinstance(api_key, str):
            return False, "Gemini API key cannot be empty"

        api_key = api_key.strip()

        # Check basic format
        if not ConfigValidator.GEMINI_API_KEY_PATTERN.match(api_key):
            return False, "Invalid Gemini API key format. Expected format: AIza... (39 characters total)"

        return True, "Valid Gemini API key format"

    @staticmethod
    def validate_file_path(path: str, must_exist: bool = False, must_be_writable: bool = False) -> Tuple[bool, str]:
        """Validate file path."""
        if not path or not isinstance(path, str):
            return False, "File path cannot be empty"

        try:
            path_obj = Path(path).resolve()

            # Check if path must exist
            if must_exist and not path_obj.exists():
                return False, f"Path does not exist: {path_obj}"

            # Check if directory exists or can be created
            if not path_obj.parent.exists():
                try:
                    path_obj.parent.mkdir(parents=True, exist_ok=True)
                except PermissionError:
                    return False, f"Cannot create directory: {path_obj.parent}"

            # Check write permissions
            if must_be_writable:
                if path_obj.exists() and not os.access(path_obj, os.W_OK):
                    return False, f"Path is not writable: {path_obj}"
                elif not path_obj.exists() and not os.access(path_obj.parent, os.W_OK):
                    return False, f"Parent directory is not writable: {path_obj.parent}"

            return True, f"Valid path: {path_obj}"

        except Exception as e:
            return False, f"Invalid path: {str(e)}"

    @staticmethod
    def validate_config(config: Dict[str, Any]) -> List[str]:
        """Validate complete configuration dictionary."""
        errors = []

        # Validate database URL
        if "DATABASE_URL" in config:
            is_valid, message = ConfigValidator.validate_database_url(config["DATABASE_URL"])
            if not is_valid:
                errors.append(f"DATABASE_URL: {message}")
        else:
            errors.append("DATABASE_URL: Required configuration missing")

        # Validate Gemini API key
        if "GEMINI_API_KEY" in config:
            is_valid, message = ConfigValidator.validate_gemini_api_key(config["GEMINI_API_KEY"])
            if not is_valid:
                errors.append(f"GEMINI_API_KEY: {message}")
        else:
            errors.append("GEMINI_API_KEY: Required configuration missing")

        # Validate paths
        for path_key in ["OUTPUT_PATH", "FILE_STORE_PATH"]:
            if path_key in config:
                is_valid, message = ConfigValidator.validate_file_path(config[path_key], must_be_writable=True)
                if not is_valid:
                    errors.append(f"{path_key}: {message}")

        return errors


class CLIValidator:
    """Validates CLI arguments and inputs."""

    @staticmethod
    def validate_natural_language_query(query: str) -> Tuple[bool, str]:
        """Validate natural language query input."""
        if not query or not isinstance(query, str):
            return False, "Query cannot be empty"

        query = query.strip()

        if len(query) < 3:
            return False, "Query must be at least 3 characters long"

        if len(query) > 1000:
            return False, "Query is too long (maximum 1000 characters)"

        # Check for potential SQL injection patterns
        dangerous_patterns = [
            r";\s*(drop|delete|truncate|alter|create|insert|update)\s+",
            r"--",
            r"/\*.*\*/",
            r"xp_cmdshell",
            r"sp_executesql",
            r"'\s*(or|and)\s*'",  # Common SQL injection like '1'='1' or 'a'='a'
            r"'\s*(or|and)\s*\d+\s*=\s*\d+",  # Patterns like ' OR 1=1
            r"'\s*or\s+true\s*",  # ' OR true
            r"union\s+select",  # UNION SELECT attacks
            r"'\s*;\s*exec",  # Command execution attempts
            r"'\s*;\s*declare",  # SQL Server specific attacks
            r"into\s+outfile",  # MySQL file writing
            r"load_file\s*\(",  # MySQL file reading
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return False, "Query contains potentially dangerous SQL patterns"

        return True, "Valid natural language query"

    @staticmethod
    def validate_output_format(format_type: str) -> Tuple[bool, str]:
        """Validate output format type."""
        if not format_type:
            return True, "No format specified (default will be used)"

        valid_formats = {"csv", "excel", "sqlite", "json", "table"}

        if format_type.lower() not in valid_formats:
            return False, f"Invalid output format. Supported: {', '.join(valid_formats)}"

        return True, f"Valid output format: {format_type}"

    @staticmethod
    def validate_save_path(save_path: str, format_type: str) -> Tuple[bool, str]:
        """Validate save path for specific format."""
        if not save_path:
            return False, "Save path cannot be empty"

        # Check file extension matches format
        path_obj = Path(save_path)
        extension = path_obj.suffix.lower()

        expected_extensions = {
            "csv": [".csv"],
            "excel": [".xlsx", ".xls"],
            "sqlite": [".db", ".sqlite", ".sqlite3"],
            "json": [".json"],
        }

        if format_type in expected_extensions:
            if extension not in expected_extensions[format_type]:
                return (
                    False,
                    f"File extension {extension} doesn't match format {format_type}. "
                    f"Expected: {', '.join(expected_extensions[format_type])}",
                )

        # Validate path
        return ConfigValidator.validate_file_path(save_path, must_be_writable=True)


def validate_production_readiness(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Comprehensive production readiness validation."""
    issues = []

    # Validate configuration
    config_errors = ConfigValidator.validate_config(config)
    issues.extend(config_errors)

    # Test database connection if URL is valid
    if "DATABASE_URL" in config and not any("DATABASE_URL" in error for error in config_errors):
        is_connected, message = ConfigValidator.validate_database_connection(config["DATABASE_URL"])
        if not is_connected:
            issues.append(f"Database Connection: {message}")

    # Check for development vs production settings
    if "DATABASE_URL" in config:
        db_url = config["DATABASE_URL"]
        if "localhost" in db_url or "127.0.0.1" in db_url:
            issues.append("WARNING: Database URL points to localhost (development setup)")

    # Validate required directories exist
    required_dirs = []
    if "OUTPUT_PATH" in config:
        required_dirs.append(config["OUTPUT_PATH"])
    if "FILE_STORE_PATH" in config:
        required_dirs.append(config["FILE_STORE_PATH"])

    for dir_path in required_dirs:
        try:
            Path(dir_path).parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            issues.append(f"Directory creation failed for {dir_path}: {str(e)}")

    is_ready = len(issues) == 0
    return is_ready, issues


def validate_environment() -> Tuple[bool, List[str]]:
    """Validate the runtime environment for production readiness."""
    issues = []

    # Check Python version
    import sys

    if sys.version_info < (3, 9):
        issues.append(f"Python version {sys.version_info[0]}.{sys.version_info[1]} is not supported. Minimum: 3.9")

    # Check required packages
    required_packages = [
        "sqlalchemy",
        "typer",
        "rich",
        "langchain",
        "psycopg2",
        "dotenv",  # Changed from python-dotenv to dotenv (the import name)
    ]

    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            issues.append(f"Required package not installed: {package}")

    return len(issues) == 0, issues
