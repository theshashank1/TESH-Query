"""Unit tests for utils modules."""

import json
import os
import tempfile
from unittest.mock import Mock, patch, mock_open
import pytest

from teshq.utils.config import (
    get_config_with_source,
    save_config,
    get_database_url,
    get_config,
    is_configured,
    DEFAULT_GEMINI_MODEL
)
from teshq.utils.formater import print_query_table, print_simple_table


class TestConfigUtils:
    """Test cases for configuration utilities."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Clear environment variables
        self.env_vars_to_restore = {}
        for var in ["DATABASE_URL", "GEMINI_API_KEY", "GEMINI_MODEL_NAME"]:
            if var in os.environ:
                self.env_vars_to_restore[var] = os.environ[var]
                del os.environ[var]

    def teardown_method(self):
        """Clean up after each test method."""
        # Restore environment variables
        for var, value in self.env_vars_to_restore.items():
            os.environ[var] = value
        
        # Clear any new environment variables
        for var in ["DATABASE_URL", "GEMINI_API_KEY", "GEMINI_MODEL_NAME"]:
            if var in os.environ and var not in self.env_vars_to_restore:
                del os.environ[var]

    @patch("os.path.exists")
    def test_get_config_from_env(self, mock_exists):
        """Test getting config from environment variables."""
        # Set environment variable
        os.environ["DATABASE_URL"] = "sqlite:///test.db"
        mock_exists.return_value = False  # No config files exist
        
        config = get_config()
        
        assert config.get("DATABASE_URL") == "sqlite:///test.db"

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    def test_get_config_from_env_file(self, mock_file, mock_exists):
        """Test getting config from .env file."""
        mock_exists.side_effect = lambda path: path == ".env"
        mock_file.return_value.read.return_value = "DATABASE_URL=sqlite:///from_env_file.db\n"
        
        config = get_config()
        
        assert config.get("DATABASE_URL") == "sqlite:///from_env_file.db"

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    def test_get_config_from_json(self, mock_file, mock_exists):
        """Test getting config from config.json file."""
        mock_exists.side_effect = lambda path: path == "config.json"
        mock_file.return_value.read.return_value = json.dumps({
            "DATABASE_URL": "sqlite:///from_json.db"
        })
        
        config = get_config()
        
        assert config.get("DATABASE_URL") == "sqlite:///from_json.db"

    @patch("os.path.exists")
    def test_get_config_with_source_env(self, mock_exists):
        """Test getting config with source information from env."""
        os.environ["DATABASE_URL"] = "sqlite:///test.db"
        mock_exists.return_value = False  # No config files exist
        
        config, sources = get_config_with_source()
        
        assert config.get("DATABASE_URL") == "sqlite:///test.db"
        assert sources.get("DATABASE_URL") == "environment"

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.makedirs")
    def test_save_config(self, mock_makedirs, mock_file):
        """Test saving configuration."""
        config = {
            "DATABASE_URL": "sqlite:///test.db",
            "GEMINI_API_KEY": "test_key"
        }
        
        result = save_config(config)
        
        # Should return True for successful save
        assert result is True
        # Verify file operations were called
        mock_file.assert_called()

    @patch("teshq.utils.config.get_config")
    def test_get_database_url(self, mock_get_config):
        """Test getting database URL."""
        mock_get_config.return_value = {"DATABASE_URL": "sqlite:///test.db"}
        
        url = get_database_url()
        
        assert url == "sqlite:///test.db"

    @patch("teshq.utils.config.get_config")
    def test_get_database_url_not_found(self, mock_get_config):
        """Test getting database URL when not configured."""
        mock_get_config.return_value = {}
        
        url = get_database_url()
        
        assert url is None

    @patch("teshq.utils.config.get_config")
    def test_is_configured_true(self, mock_get_config):
        """Test configuration check when properly configured."""
        mock_get_config.return_value = {
            "DATABASE_URL": "sqlite:///test.db",
            "GEMINI_API_KEY": "test_key"
        }
        
        result = is_configured()
        
        assert result is True

    @patch("teshq.utils.config.get_config")
    def test_is_configured_false(self, mock_get_config):
        """Test configuration check when not configured."""
        mock_get_config.return_value = {
            "DATABASE_URL": "sqlite:///test.db"
            # Missing GEMINI_API_KEY
        }
        
        result = is_configured()
        
        assert result is False


class TestFormatterUtils:
    """Test cases for formatter utilities."""

    def test_print_query_table_basic(self, capsys):
        """Test basic query table printing."""
        request = "Find all users"
        query = "SELECT * FROM users"
        params = {"limit": 10}
        results = [
            {"id": 1, "name": "John", "age": 25},
            {"id": 2, "name": "Jane", "age": 30}
        ]
        
        print_query_table(request, query, params, results)
        
        captured = capsys.readouterr()
        assert len(captured.out) > 0
        # Should contain some output (basic smoke test)

    def test_print_query_table_empty_results(self, capsys):
        """Test query table printing with empty results."""
        request = "Find non-existent data"
        query = "SELECT * FROM users WHERE id = -1"
        params = {}
        results = []
        
        print_query_table(request, query, params, results)
        
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_print_simple_table_basic(self, capsys):
        """Test basic simple table printing."""
        results = [
            {"name": "Alice", "score": 95},
            {"name": "Bob", "score": 87}
        ]
        title = "Test Scores"
        
        print_simple_table(results, title)
        
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_print_simple_table_empty(self, capsys):
        """Test simple table printing with empty data."""
        results = []
        title = "Empty Table"
        
        print_simple_table(results, title)
        
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_print_simple_table_none_results(self, capsys):
        """Test simple table printing with None results."""
        results = None
        title = "None Results"
        
        # Should handle None gracefully
        print_simple_table(results, title)
        
        captured = capsys.readouterr()
        assert len(captured.out) > 0