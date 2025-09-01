"""Unit tests for validation utilities."""

import pytest
from unittest.mock import patch, Mock

from teshq.utils.validation import (
    ValidationError,
    validate_database_url,
    test_database_connection,
    validate_gemini_api_key,
    validate_file_path,
    validate_query_parameters,
    validate_sql_query,
    validate_model_name,
    validate_config_data,
    validate_cli_integer,
    validate_cli_choice
)


class TestDatabaseValidation:
    """Test cases for database validation."""

    def test_validate_database_url_valid_sqlite(self):
        """Test valid SQLite URL."""
        url = "sqlite:///test.db"
        result = validate_database_url(url)
        assert result == url

    def test_validate_database_url_valid_postgresql(self):
        """Test valid PostgreSQL URL."""
        url = "postgresql://user:pass@localhost:5432/dbname"
        result = validate_database_url(url)
        assert result == url

    def test_validate_database_url_valid_mysql(self):
        """Test valid MySQL URL."""
        url = "mysql://user:pass@localhost:3306/dbname"
        result = validate_database_url(url)
        assert result == url

    def test_validate_database_url_empty(self):
        """Test empty URL raises error."""
        with pytest.raises(ValidationError, match="Database URL must be a non-empty string"):
            validate_database_url("")

    def test_validate_database_url_none(self):
        """Test None URL raises error."""
        with pytest.raises(ValidationError, match="Database URL must be a non-empty string"):
            validate_database_url(None)

    def test_validate_database_url_unsupported_scheme(self):
        """Test unsupported database scheme."""
        with pytest.raises(ValidationError, match="Unsupported database scheme"):
            validate_database_url("mongodb://localhost:27017/test")

    def test_validate_database_url_invalid_format(self):
        """Test invalid URL format."""
        with pytest.raises(ValidationError, match="Invalid SQLAlchemy URL format"):
            validate_database_url("not-a-valid-url")

    @patch('teshq.utils.validation.create_engine')
    def test_database_connection_success(self, mock_create_engine):
        """Test successful database connection."""
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine
        
        mock_conn = Mock()
        mock_context_manager = Mock()
        mock_context_manager.__enter__ = Mock(return_value=mock_conn)
        mock_context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = mock_context_manager
        
        result = test_database_connection("sqlite:///test.db")
        assert result is True

    @patch('teshq.utils.validation.create_engine')
    def test_database_connection_failure(self, mock_create_engine):
        """Test failed database connection."""
        mock_create_engine.side_effect = Exception("Connection failed")
        
        result = test_database_connection("sqlite:///nonexistent.db")
        assert result is False


class TestAPIKeyValidation:
    """Test cases for API key validation."""

    def test_validate_gemini_api_key_valid(self):
        """Test valid API key."""
        api_key = "AIzaSyBc123456789abcdefghijklmnop-qrstuvw"
        result = validate_gemini_api_key(api_key)
        assert result == api_key

    def test_validate_gemini_api_key_with_spaces(self):
        """Test API key with leading/trailing spaces."""
        api_key = "  AIzaSyBc123456789abcdefghijklmnop-qrstuvw  "
        result = validate_gemini_api_key(api_key)
        assert result == api_key.strip()

    def test_validate_gemini_api_key_empty(self):
        """Test empty API key raises error."""
        with pytest.raises(ValidationError, match="API key must be a non-empty string"):
            validate_gemini_api_key("")

    def test_validate_gemini_api_key_none(self):
        """Test None API key raises error."""
        with pytest.raises(ValidationError, match="API key must be a non-empty string"):
            validate_gemini_api_key(None)

    def test_validate_gemini_api_key_invalid_format(self):
        """Test invalid API key format."""
        with pytest.raises(ValidationError, match="API key format appears invalid"):
            validate_gemini_api_key("invalid-key")

    def test_validate_gemini_api_key_too_short(self):
        """Test too short API key."""
        with pytest.raises(ValidationError, match="API key format appears invalid"):
            validate_gemini_api_key("short")


class TestFilePathValidation:
    """Test cases for file path validation."""

    @patch('os.path.exists')
    @patch('os.access')
    def test_validate_file_path_valid(self, mock_access, mock_exists):
        """Test valid file path."""
        mock_exists.return_value = True
        mock_access.return_value = True
        
        path = "/tmp/test/file.txt"
        result = validate_file_path(path)
        assert result.endswith("file.txt")

    def test_validate_file_path_empty(self):
        """Test empty file path raises error."""
        with pytest.raises(ValidationError, match="File path must be a non-empty string"):
            validate_file_path("")

    @patch('os.path.exists')
    def test_validate_file_path_parent_not_exists(self, mock_exists):
        """Test file path with non-existent parent directory."""
        mock_exists.return_value = False
        
        with pytest.raises(ValidationError, match="Parent directory does not exist"):
            validate_file_path("/nonexistent/dir/file.txt")

    @patch('os.path.exists')
    @patch('os.access')
    def test_validate_file_path_not_writable(self, mock_access, mock_exists):
        """Test file path with non-writable parent directory."""
        mock_exists.return_value = True
        mock_access.return_value = False
        
        with pytest.raises(ValidationError, match="Parent directory is not writable"):
            validate_file_path("/readonly/dir/file.txt")


class TestQueryValidation:
    """Test cases for query validation."""

    def test_validate_query_parameters_valid(self):
        """Test valid query parameters."""
        params = {"user_id": 123, "name": "John", "active": True}
        result = validate_query_parameters(params)
        assert result == params

    def test_validate_query_parameters_none(self):
        """Test None parameters returns empty dict."""
        result = validate_query_parameters(None)
        assert result == {}

    def test_validate_query_parameters_not_dict(self):
        """Test non-dict parameters raises error."""
        with pytest.raises(ValidationError, match="Query parameters must be a dictionary"):
            validate_query_parameters("not a dict")

    def test_validate_query_parameters_dangerous_key(self):
        """Test parameters with dangerous key names."""
        with pytest.raises(ValidationError, match="Parameter name contains suspicious pattern"):
            validate_query_parameters({"DROP_TABLE": "value"})

    def test_validate_query_parameters_invalid_key_format(self):
        """Test parameters with invalid key format."""
        with pytest.raises(ValidationError, match="Invalid parameter name format"):
            validate_query_parameters({"123invalid": "value"})

    def test_validate_query_parameters_invalid_value_type(self):
        """Test parameters with invalid value type."""
        with pytest.raises(ValidationError, match="Parameter value type not supported"):
            validate_query_parameters({"key": {"nested": "dict"}})

    def test_validate_sql_query_valid_select(self):
        """Test valid SELECT query."""
        query = "SELECT * FROM users WHERE id = :user_id"
        result = validate_sql_query(query)
        assert result == query

    def test_validate_sql_query_empty(self):
        """Test empty query raises error."""
        with pytest.raises(ValidationError, match="SQL query must be a non-empty string"):
            validate_sql_query("")

    def test_validate_sql_query_not_select(self):
        """Test non-SELECT query raises error."""
        with pytest.raises(ValidationError, match="Only SELECT queries are allowed"):
            validate_sql_query("INSERT INTO users VALUES (1, 'John')")

    def test_validate_sql_query_dangerous_drop(self):
        """Test query with DROP statement."""
        with pytest.raises(ValidationError, match="Query contains potentially dangerous pattern"):
            validate_sql_query("SELECT * FROM users; DROP TABLE users;")

    def test_validate_sql_query_dangerous_delete_all(self):
        """Test query with dangerous DELETE WHERE 1=1."""
        with pytest.raises(ValidationError, match="Query contains potentially dangerous pattern"):
            validate_sql_query("SELECT 1; DELETE FROM users WHERE 1=1")


class TestModelValidation:
    """Test cases for model validation."""

    def test_validate_model_name_valid(self):
        """Test valid model names."""
        valid_models = [
            'gemini-1.5-flash',
            'gemini-1.5-pro',
            'gemini-2.0-flash-lite'
        ]
        
        for model in valid_models:
            result = validate_model_name(model)
            assert result == model

    def test_validate_model_name_empty(self):
        """Test empty model name raises error."""
        with pytest.raises(ValidationError, match="Model name must be a non-empty string"):
            validate_model_name("")

    def test_validate_model_name_invalid(self):
        """Test invalid model name."""
        with pytest.raises(ValidationError, match="Unknown model name"):
            validate_model_name("invalid-model-name")

    def test_validate_model_name_with_spaces(self):
        """Test model name with spaces gets stripped."""
        result = validate_model_name("  gemini-1.5-flash  ")
        assert result == "gemini-1.5-flash"


class TestConfigValidation:
    """Test cases for configuration validation."""

    @patch('teshq.utils.validation.validate_database_url')
    @patch('teshq.utils.validation.validate_gemini_api_key')
    @patch('teshq.utils.validation.validate_model_name')
    def test_validate_config_data_complete(self, mock_model, mock_api_key, mock_db_url):
        """Test complete configuration validation."""
        mock_db_url.return_value = "sqlite:///test.db"
        mock_api_key.return_value = "valid_api_key"
        mock_model.return_value = "gemini-1.5-flash"
        
        config = {
            "DATABASE_URL": "sqlite:///test.db",
            "GEMINI_API_KEY": "valid_api_key",
            "GEMINI_MODEL_NAME": "gemini-1.5-flash"
        }
        
        result = validate_config_data(config)
        
        assert result["DATABASE_URL"] == "sqlite:///test.db"
        assert result["GEMINI_API_KEY"] == "valid_api_key"
        assert result["GEMINI_MODEL_NAME"] == "gemini-1.5-flash"

    def test_validate_config_data_not_dict(self):
        """Test non-dict configuration raises error."""
        with pytest.raises(ValidationError, match="Configuration must be a dictionary"):
            validate_config_data("not a dict")

    def test_validate_config_data_empty(self):
        """Test empty configuration returns empty dict."""
        result = validate_config_data({})
        assert result == {}


class TestCLIValidation:
    """Test cases for CLI argument validation."""

    def test_validate_cli_integer_valid(self):
        """Test valid CLI integer."""
        result = validate_cli_integer("42")
        assert result == 42

    def test_validate_cli_integer_invalid(self):
        """Test invalid CLI integer."""
        with pytest.raises(ValidationError, match="Invalid integer value"):
            validate_cli_integer("not_a_number")

    def test_validate_cli_integer_with_min_max(self):
        """Test CLI integer with min/max constraints."""
        result = validate_cli_integer("50", min_val=1, max_val=100)
        assert result == 50

    def test_validate_cli_integer_below_min(self):
        """Test CLI integer below minimum."""
        with pytest.raises(ValidationError, match="Value must be >= 10"):
            validate_cli_integer("5", min_val=10)

    def test_validate_cli_integer_above_max(self):
        """Test CLI integer above maximum."""
        with pytest.raises(ValidationError, match="Value must be <= 100"):
            validate_cli_integer("150", max_val=100)

    def test_validate_cli_choice_valid(self):
        """Test valid CLI choice."""
        choices = ["dev", "staging", "prod"]
        result = validate_cli_choice("dev", choices)
        assert result == "dev"

    def test_validate_cli_choice_invalid(self):
        """Test invalid CLI choice."""
        choices = ["dev", "staging", "prod"]
        with pytest.raises(ValidationError, match="Invalid choice 'invalid'"):
            validate_cli_choice("invalid", choices)