"""
Comprehensive tests for input validation system.

Tests all validation functions to ensure production-ready input handling.
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import SQLAlchemyError

from teshq.utils.validation import (
    CLIValidator,
    ConfigValidator,
    ValidationError,
    validate_environment,
    validate_production_readiness,
)


class TestConfigValidator:
    """Test configuration validation functionality."""

    def test_validate_database_url_valid_sqlite(self):
        """Test valid SQLite database URL."""
        is_valid, message = ConfigValidator.validate_database_url("sqlite:///test.db")
        assert is_valid
        assert "Valid database URL format" in message

    def test_validate_database_url_valid_postgresql(self):
        """Test valid PostgreSQL database URL."""
        url = "postgresql://user:password@localhost:5432/testdb"
        is_valid, message = ConfigValidator.validate_database_url(url)
        assert is_valid
        assert "Valid database URL format" in message

    def test_validate_database_url_invalid_empty(self):
        """Test invalid empty database URL."""
        is_valid, message = ConfigValidator.validate_database_url("")
        assert not is_valid
        assert "cannot be empty" in message

    def test_validate_database_url_invalid_scheme(self):
        """Test invalid database scheme."""
        is_valid, message = ConfigValidator.validate_database_url("oracle://user@host/db")
        assert not is_valid
        assert "Unsupported database type" in message

    def test_validate_database_url_missing_hostname(self):
        """Test missing hostname for non-SQLite database."""
        is_valid, message = ConfigValidator.validate_database_url("postgresql:///testdb")
        assert not is_valid
        assert "must include hostname" in message

    def test_validate_gemini_api_key_valid(self):
        """Test valid Gemini API key format."""
        valid_key = "AIza" + "A" * 35  # 39 characters total
        is_valid, message = ConfigValidator.validate_gemini_api_key(valid_key)
        assert is_valid
        assert "Valid Gemini API key format" in message

    def test_validate_gemini_api_key_invalid_format(self):
        """Test invalid Gemini API key format."""
        is_valid, message = ConfigValidator.validate_gemini_api_key("invalid_key")
        assert not is_valid
        assert "Invalid Gemini API key format" in message

    def test_validate_gemini_api_key_empty(self):
        """Test empty Gemini API key."""
        is_valid, message = ConfigValidator.validate_gemini_api_key("")
        assert not is_valid
        assert "cannot be empty" in message

    def test_validate_file_path_valid(self):
        """Test valid file path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = os.path.join(temp_dir, "test_file.txt")
            is_valid, message = ConfigValidator.validate_file_path(test_path)
            assert is_valid
            assert "Valid path" in message

    def test_validate_file_path_must_exist_missing(self):
        """Test file path that must exist but doesn't."""
        is_valid, message = ConfigValidator.validate_file_path("/nonexistent/path.txt", must_exist=True)
        assert not is_valid
        assert "does not exist" in message

    def test_validate_config_complete_valid(self):
        """Test complete valid configuration."""
        config = {
            "DATABASE_URL": "sqlite:///test.db",
            "GEMINI_API_KEY": "AIza" + "A" * 35,
            "OUTPUT_PATH": "/tmp/output",
            "FILE_STORE_PATH": "/tmp/files",
        }

        with patch.object(ConfigValidator, "validate_file_path", return_value=(True, "Valid path")):
            errors = ConfigValidator.validate_config(config)
            assert len(errors) == 0

    def test_validate_config_missing_required(self):
        """Test configuration missing required fields."""
        config = {}
        errors = ConfigValidator.validate_config(config)
        assert len(errors) >= 2  # DATABASE_URL and GEMINI_API_KEY required
        assert any("DATABASE_URL" in error for error in errors)
        assert any("GEMINI_API_KEY" in error for error in errors)

    def test_validate_config_invalid_values(self):
        """Test configuration with invalid values."""
        config = {
            "DATABASE_URL": "invalid_url",
            "GEMINI_API_KEY": "invalid_key",
        }
        errors = ConfigValidator.validate_config(config)
        assert len(errors) >= 2
        assert any("DATABASE_URL" in error for error in errors)
        assert any("GEMINI_API_KEY" in error for error in errors)

    @patch("teshq.utils.validation.create_engine")
    def test_validate_database_connection_success(self, mock_create_engine):
        """Test successful database connection."""
        # Mock successful connection
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        mock_create_engine.return_value = mock_engine

        is_connected, message = ConfigValidator.validate_database_connection("sqlite:///test.db")
        assert is_connected
        assert "successful" in message

    @patch("teshq.utils.validation.create_engine")
    def test_validate_database_connection_failure(self, mock_create_engine):
        """Test failed database connection."""
        # Mock connection failure
        mock_create_engine.side_effect = SQLAlchemyError("Connection failed")

        is_connected, message = ConfigValidator.validate_database_connection("postgresql://invalid")
        assert not is_connected
        assert "failed" in message


class TestCLIValidator:
    """Test CLI input validation functionality."""

    def test_validate_natural_language_query_valid(self):
        """Test valid natural language query."""
        query = "Show me all users with age greater than 25"
        is_valid, message = CLIValidator.validate_natural_language_query(query)
        assert is_valid
        assert "Valid natural language query" in message

    def test_validate_natural_language_query_empty(self):
        """Test empty query."""
        is_valid, message = CLIValidator.validate_natural_language_query("")
        assert not is_valid
        assert "cannot be empty" in message

    def test_validate_natural_language_query_too_short(self):
        """Test query that is too short."""
        is_valid, message = CLIValidator.validate_natural_language_query("Hi")
        assert not is_valid
        assert "at least 3 characters" in message

    def test_validate_natural_language_query_too_long(self):
        """Test query that is too long."""
        long_query = "x" * 1001
        is_valid, message = CLIValidator.validate_natural_language_query(long_query)
        assert not is_valid
        assert "too long" in message

    def test_validate_natural_language_query_sql_injection(self):
        """Test query with potential SQL injection."""
        dangerous_query = "Show users; DROP TABLE users; --"
        is_valid, message = CLIValidator.validate_natural_language_query(dangerous_query)
        assert not is_valid
        assert "dangerous SQL patterns" in message

    def test_validate_output_format_valid(self):
        """Test valid output formats."""
        valid_formats = ["csv", "excel", "sqlite", "json", "table"]
        for format_type in valid_formats:
            is_valid, message = CLIValidator.validate_output_format(format_type)
            assert is_valid, f"Format {format_type} should be valid"

    def test_validate_output_format_invalid(self):
        """Test invalid output format."""
        is_valid, message = CLIValidator.validate_output_format("invalid_format")
        assert not is_valid
        assert "Invalid output format" in message

    def test_validate_save_path_csv_valid(self):
        """Test valid CSV save path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "output.csv")
            is_valid, message = CLIValidator.validate_save_path(csv_path, "csv")
            assert is_valid

    def test_validate_save_path_wrong_extension(self):
        """Test save path with wrong extension."""
        is_valid, message = CLIValidator.validate_save_path("output.txt", "csv")
        assert not is_valid
        assert "doesn't match format" in message

    def test_validate_save_path_empty(self):
        """Test empty save path."""
        is_valid, message = CLIValidator.validate_save_path("", "csv")
        assert not is_valid
        assert "cannot be empty" in message


class TestProductionReadiness:
    """Test production readiness validation."""

    def test_validate_production_readiness_valid_config(self):
        """Test production readiness with valid configuration."""
        config = {
            "DATABASE_URL": "postgresql://user:pass@production-host:5432/db",
            "GEMINI_API_KEY": "AIza" + "A" * 35,
            "OUTPUT_PATH": "/tmp/output",
            "FILE_STORE_PATH": "/tmp/files",
        }

        with patch.object(ConfigValidator, "validate_database_connection", return_value=(True, "Success")):
            with patch.object(ConfigValidator, "validate_config", return_value=[]):
                is_ready, issues = validate_production_readiness(config)
                assert is_ready
                assert len(issues) == 0

    def test_validate_production_readiness_localhost_warning(self):
        """Test production readiness with localhost database (warning)."""
        config = {
            "DATABASE_URL": "postgresql://user:pass@localhost:5432/db",
            "GEMINI_API_KEY": "AIza" + "A" * 35,
        }

        with patch.object(ConfigValidator, "validate_database_connection", return_value=(True, "Success")):
            with patch.object(ConfigValidator, "validate_config", return_value=[]):
                is_ready, issues = validate_production_readiness(config)
                assert not is_ready  # Should fail due to localhost warning
                assert any("localhost" in issue for issue in issues)

    def test_validate_production_readiness_connection_failure(self):
        """Test production readiness with connection failure."""
        config = {
            "DATABASE_URL": "postgresql://user:pass@host:5432/db",
            "GEMINI_API_KEY": "AIza" + "A" * 35,
        }

        with patch.object(ConfigValidator, "validate_database_connection", return_value=(False, "Connection failed")):
            with patch.object(ConfigValidator, "validate_config", return_value=[]):
                is_ready, issues = validate_production_readiness(config)
                assert not is_ready
                assert any("Connection failed" in issue for issue in issues)


class TestEnvironmentValidation:
    """Test environment validation for production readiness."""

    def test_validate_environment_success(self):
        """Test successful environment validation."""
        # This test assumes we're running in a proper environment
        is_valid, issues = validate_environment()
        # We expect this to pass in our test environment
        if not is_valid:
            # Print issues for debugging
            print("Environment validation issues:", issues)
        assert is_valid or len(issues) == 0  # Allow either success or no critical issues

    @patch("sys.version_info", (3, 8, 0))  # Mock Python 3.8
    def test_validate_environment_old_python(self):
        """Test environment validation with old Python version."""
        is_valid, issues = validate_environment()
        assert not is_valid
        assert any("Python version" in issue for issue in issues)


class TestValidationError:
    """Test custom ValidationError exception."""

    def test_validation_error_creation(self):
        """Test ValidationError can be created with message and field."""
        error = ValidationError("Test message", "test_field")
        assert str(error) == "Test message"
        assert error.field == "test_field"
        assert error.message == "Test message"

    def test_validation_error_no_field(self):
        """Test ValidationError can be created without field."""
        error = ValidationError("Test message")
        assert str(error) == "Test message"
        assert error.field is None
        assert error.message == "Test message"
