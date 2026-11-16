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

from teshq.core.connectors import UnifiedDatabaseConnector


class ValidationError(Exception):
    """Custom exception for validation errors."""

    def __init__(self, message: str, field: str = None):
        super().__init__(message)
        self.field = field
        self.message = message


class ConfigValidator:
    """Validates configuration values for production readiness."""

    # Use unified connector's supported database list
    SUPPORTED_DB_TYPES: set = set(UnifiedDatabaseConnector.get_supported_databases())
    GEMINI_API_KEY_PATTERN = re.compile(r"^(AIza[0-9A-Za-z\-_]{35,}|AQ\.[0-9A-Za-z\-_.]{20,})$")

    @staticmethod
    def validate_database_url(db_url: str) -> Tuple[bool, str]:
        """Validate database URL format supporting all SQLAlchemy database dialects."""
        if not db_url or not isinstance(db_url, str):
            return False, "Database URL cannot be empty"

        db_url = db_url.strip()

        try:
            from sqlalchemy.engine import make_url
            parsed_url = None
            try:
                parsed_url = make_url(db_url)
                backend = parsed_url.get_backend_name().lower()
            except Exception:
                parsed = urlparse(db_url)
                if not parsed.scheme:
                    return False, "Database URL must include a scheme (postgresql://, mysql://, sqlite://, etc.)"
                backend = parsed.scheme.lower().split("+")[0]

            if not backend:
                return False, "Database URL must include a scheme (postgresql://, mysql://, sqlite://, etc.)"

            # Validate detected database type
            detected_type = backend
            if detected_type in ("postgres", "cockroachdb"):
                detected_type = "postgresql"
            elif detected_type in ("sqlserver", "mssql"):
                detected_type = "mssql"
            elif detected_type == "mariadb":
                detected_type = "mysql"

            # Check supported database info (always True via Generic connector)
            db_info = UnifiedDatabaseConnector.get_database_info(db_url)
            if not db_info.get("supported", False):
                supported_types = ", ".join(UnifiedDatabaseConnector.get_supported_databases())
                return False, f"Unsupported database type: {detected_type}. Supported types: {supported_types}"

            # Special validation for embedded / file-based databases: SQLite & DuckDB
            if detected_type in ("sqlite", "duckdb"):
                path_str = getattr(parsed_url, "database", None) or urlparse(db_url).path or ""
                if ":memory:" in db_url or path_str == ":memory:":
                    return True, f"Valid {detected_type} database URL format"
                if path_str:
                    import os
                    if path_str.startswith("//"):
                        db_path = Path(path_str[1:])
                    elif path_str.startswith("/"):
                        db_path = Path.cwd() / path_str[1:]
                    else:
                        db_path = Path.cwd() / path_str
                    parent = db_path.parent
                    if not parent.exists():
                        return False, f"Directory for {detected_type.capitalize()} database does not exist: {parent}"
                    if not os.access(parent, os.W_OK):
                        return False, f"Directory for {detected_type.capitalize()} database is not writable: {parent}"
                else:
                    return False, f"{detected_type.capitalize()} URL must include a path to the database file"

            # For network / client-server databases
            else:
                host = getattr(parsed_url, "host", None)
                parsed_fb = urlparse(db_url)
                if not host and not parsed_fb.hostname and not parsed_fb.netloc:
                    return False, f"{detected_type} database URL must include hostname"
                database = getattr(parsed_url, "database", None) or parsed_fb.path
                if not database or database == "/":
                    if detected_type not in ("snowflake", "bigquery", "clickhouse", "teradata", "duckdb"):
                        return False, f"{detected_type} database URL must include database name"

            return True, f"Valid {backend} database URL format"

        except Exception as e:
            return False, f"Invalid database URL format: {str(e)}"

    @staticmethod
    def validate_database_connection(db_url: str) -> Tuple[bool, str]:
        """Test actual database connection using unified connector system."""
        try:
            # Use unified connector for comprehensive connection testing
            success, message = UnifiedDatabaseConnector.test_connection(db_url)
            return success, message

        except Exception as e:
            return False, f"Connection test failed: {str(e)}"

    @staticmethod
    def validate_gemini_api_key(api_key: str) -> Tuple[bool, str]:
        """Validate Gemini API key format."""
        if not api_key or not isinstance(api_key, str):
            return False, "Gemini API key cannot be empty"

        api_key = api_key.strip()

        # Check basic format
        if not ConfigValidator.GEMINI_API_KEY_PATTERN.match(api_key):
            return False, "Invalid Gemini API key format. Expected Google API key (starting with 'AIza' or 'AQ.')"

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

            # Check if directory exists
            if not path_obj.parent.exists():
                return False, f"Directory does not exist: {path_obj.parent}"

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
        """Validate complete configuration dictionary — provider-aware."""
        errors = []

        # Validate database URL
        if "DATABASE_URL" in config:
            is_valid, message = ConfigValidator.validate_database_url(config["DATABASE_URL"])
            if not is_valid:
                errors.append(f"DATABASE_URL: {message}")
        else:
            errors.append("DATABASE_URL: Required configuration missing")

        # Determine provider from config
        provider = (config.get("LLM_PROVIDER") or "google").lower().strip()

        # Auto-detect: if Azure credentials present and Gemini key absent, use Azure
        has_azure = bool(
            config.get("AZURE_OPENAI_API_KEY")
            and config.get("AZURE_OPENAI_ENDPOINT")
            and config.get("AZURE_OPENAI_DEPLOYMENT")
        )
        has_gemini = bool(config.get("GEMINI_API_KEY"))

        if not has_gemini and has_azure:
            provider = "azure"

        if provider == "azure":
            # Validate Azure credentials
            for key, label in [
                ("AZURE_OPENAI_API_KEY", "Azure OpenAI API Key"),
                ("AZURE_OPENAI_ENDPOINT", "Azure OpenAI Endpoint"),
                ("AZURE_OPENAI_DEPLOYMENT", "Azure OpenAI Deployment"),
            ]:
                if not config.get(key):
                    errors.append(f"{key}: {label} is required for Azure provider")
        else:
            # Validate Gemini API key
            if "GEMINI_API_KEY" in config:
                is_valid, message = ConfigValidator.validate_gemini_api_key(config["GEMINI_API_KEY"])
                if not is_valid:
                    errors.append(f"GEMINI_API_KEY: {message}")
            else:
                errors.append("GEMINI_API_KEY: Required for Google Gemini provider (or set LLM_PROVIDER=azure)")

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
            r";\s*(drop|delete|truncate|alter|create|insert|update|attach|detach|grant|revoke|copy|shutdown)\s+",
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
            r"pg_read_file\s*\(",  # PostgreSQL file reading
            r"pg_ls_dir\s*\(",  # PostgreSQL directory listing
            r"sys_eval\s*\(",  # MySQL UDF code execution
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
        path_obj = Path(dir_path)
        try:
            path_exists = path_obj.exists()
        except PermissionError:
            issues.append(f"Directory access denied (insufficient permissions): {dir_path}")
            continue
        except OSError as e:
            issues.append(f"Directory is not accessible ({e.strerror}): {dir_path}")
            continue
        if not path_exists:
            issues.append(f"Directory does not exist: {dir_path}")
        elif not os.access(path_obj, os.W_OK):
            issues.append(f"Directory is not writable: {dir_path}")

    is_ready = len(issues) == 0
    return is_ready, issues


def validate_environment() -> Tuple[bool, List[str]]:
    """Validate the runtime environment for production readiness."""
    issues = []

    # Check Python version
    import sys

    if sys.version_info < (3, 9):
        issues.append(f"Python version {sys.version_info[0]}.{sys.version_info[1]} is not supported. Minimum: 3.9")

    # Check required packages (optional DB drivers like psycopg2 are excluded)
    required_packages = [
        "sqlalchemy",
        "typer",
        "rich",
        "langchain",
        "dotenv",  # python-dotenv import name
    ]

    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            issues.append(f"Required package not installed: {package}")

    return len(issues) == 0, issues
