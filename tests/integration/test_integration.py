"""Integration tests for CLI commands."""

import os
import tempfile
import json
from unittest.mock import patch, Mock
import pytest
from typer.testing import CliRunner

from teshq.cli.main import app


class TestCLIIntegration:
    """Integration tests for CLI commands."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        self.temp_dir = tempfile.mkdtemp()
        
        # Clear environment variables
        self.env_backup = {}
        for var in ["DATABASE_URL", "GEMINI_API_KEY", "GEMINI_MODEL_NAME"]:
            if var in os.environ:
                self.env_backup[var] = os.environ[var]
                del os.environ[var]

    def teardown_method(self):
        """Clean up after tests."""
        # Restore environment variables
        for var, value in self.env_backup.items():
            os.environ[var] = value

    def test_cli_version(self):
        """Test version command."""
        result = self.runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "teshq" in result.stdout

    def test_cli_developer(self):
        """Test developer command."""
        result = self.runner.invoke(app, ["--developer"])
        assert result.exit_code == 0
        assert "Shashank" in result.stdout

    def test_cli_help(self):
        """Test help command."""
        result = self.runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "TESH Query" in result.stdout

    def test_cli_name_command(self):
        """Test name command."""
        result = self.runner.invoke(app, ["name"])
        assert result.exit_code == 0
        assert "App Name" in result.stdout

    def test_cli_help_text_command(self):
        """Test help-text command."""
        result = self.runner.invoke(app, ["help-text"])
        assert result.exit_code == 0
        assert "Help:" in result.stdout


class TestConfigCLIIntegration:
    """Integration tests for config CLI commands."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        self.temp_dir = tempfile.mkdtemp()
        
        # Clear environment variables
        self.env_backup = {}
        for var in ["DATABASE_URL", "GEMINI_API_KEY", "GEMINI_MODEL_NAME"]:
            if var in os.environ:
                self.env_backup[var] = os.environ[var]
                del os.environ[var]

    def teardown_method(self):
        """Clean up after tests."""
        # Restore environment variables
        for var, value in self.env_backup.items():
            os.environ[var] = value

    @patch('teshq.cli.config.get_config_with_source')
    def test_config_display_current(self, mock_get_config):
        """Test displaying current configuration."""
        mock_get_config.return_value = (
            {"DATABASE_URL": "sqlite:///test.db"},
            {"DATABASE_URL": "environment"}
        )
        
        result = self.runner.invoke(app, ["config"])
        assert result.exit_code == 0

    @patch('teshq.cli.config.save_config')
    @patch('teshq.cli.config.get_config_with_source')
    def test_config_save_database_url(self, mock_get_config, mock_save_config):
        """Test saving database URL configuration."""
        mock_get_config.return_value = ({}, {})
        mock_save_config.return_value = True
        
        result = self.runner.invoke(app, [
            "config",
            "--database-url", "sqlite:///test.db",
            "--save"
        ])
        
        # Should complete without error
        assert result.exit_code == 0
        mock_save_config.assert_called_once()


class TestDatabaseCLIIntegration:
    """Integration tests for database CLI commands."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        
        # Clear environment variables
        self.env_backup = {}
        for var in ["DATABASE_URL", "GEMINI_API_KEY", "GEMINI_MODEL_NAME"]:
            if var in os.environ:
                self.env_backup[var] = os.environ[var]
                del os.environ[var]

    def teardown_method(self):
        """Clean up after tests."""
        # Restore environment variables
        for var, value in self.env_backup.items():
            os.environ[var] = value

    def test_db_help(self):
        """Test database command help."""
        result = self.runner.invoke(app, ["db", "--help"])
        assert result.exit_code == 0
        assert "database" in result.stdout.lower()


class TestQueryCLIIntegration:
    """Integration tests for query CLI commands."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        
        # Set up test environment
        os.environ["DATABASE_URL"] = "sqlite:///test.db"
        os.environ["GEMINI_API_KEY"] = "test_api_key"

    def teardown_method(self):
        """Clean up after tests."""
        # Clean up environment variables
        for var in ["DATABASE_URL", "GEMINI_API_KEY", "GEMINI_MODEL_NAME"]:
            if var in os.environ:
                del os.environ[var]

    def test_query_help(self):
        """Test query command help."""
        result = self.runner.invoke(app, ["query", "--help"])
        assert result.exit_code == 0
        assert "query" in result.stdout.lower()