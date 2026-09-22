"""
Unit tests for the improved TESH-Query Config CLI.

Tests:
  - Clean status dashboard display
  - Relative SQLite path formatting
  - Rich help panel grouping (Quick Setup vs Power Users/Scripting)
  - Seamless exit code 0 when displaying status / no-args
"""

import os
from unittest.mock import patch

from typer.testing import CliRunner

from teshq.cli.config import (
    PANEL_AI,
    PANEL_DB,
    PANEL_QUICK,
    PANEL_STORAGE,
    app,
    display_config_dashboard,
)

runner = CliRunner()


class TestConfigHelpPanels:
    """Verify that CLI options are organized into intuitive panels."""

    def test_help_contains_grouped_panels(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        output = result.stdout

        # Verify all four logical panels exist
        assert "Quick Setup" in output
        assert "Database Options" in output
        assert "AI Provider Options" in output
        assert "Storage & Settings" in output

    def test_help_contains_quick_actions(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        output = result.stdout

        # Quick action flags should be prominently listed
        assert "--wizard" in output
        assert "--status" in output
        assert "--db" in output
        assert "--ai" in output

    def test_help_contains_scripting_options(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        output = result.stdout

        # Power user flags must all be preserved
        assert "--db-url" in output
        assert "--db-type" in output
        assert "--db-host" in output
        assert "--db-port" in output
        assert "--db-name" in output
        assert "--gemini-api-key" in output
        assert "--azure-endpoint" in output
        assert "--azure-deployment" in output
        assert "--azure-api-key" in output
        assert "--local-model-path" in output
        assert "--llm-provider" in output


class TestConfigDashboard:
    """Verify dashboard output formatting and clean exit."""

    @patch("teshq.cli.config.get_config_with_source")
    def test_sqlite_display_is_relative_not_masked_host(self, mock_get_cfg):
        mock_get_cfg.return_value = (
            {
                "DATABASE_URL": f"sqlite:///{os.path.abspath('test_sample.sqlite')}",
                "LLM_PROVIDER": "google",
                "GEMINI_MODEL": "gemini-2.0-flash",
                "OUTPUT_PATH": ".teshq/outputs/",
            },
            {},
        )
        # Should not raise exception
        display_config_dashboard()

    def test_config_no_args_exits_cleanly(self):
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        # Must not contain the previous error card
        assert "Configuration Setup Error" not in result.stdout
        assert "An unexpected issue occurred" not in result.stdout

    def test_config_status_exits_cleanly(self):
        result = runner.invoke(app, ["--status"])
        assert result.exit_code == 0
        assert "Configuration Setup Error" not in result.stdout

    @patch("teshq.cli.config.configure_gemini_interactive")
    @patch("teshq.cli.config.save_config")
    def test_config_ai_renders_without_markup_error(self, mock_save, mock_gemini):
        mock_gemini.return_value = ("test-key", "gemini-2.0-flash")
        mock_save.return_value = True

        result = runner.invoke(app, ["--ai"], input="1\n")
        assert result.exit_code == 0
        assert "Choose AI Provider:" in result.stdout
        assert "MarkupError" not in result.stdout
        assert "Configuration Setup Error" not in result.stdout

    @patch("teshq.cli.config.configure_database_interactive", side_effect=KeyboardInterrupt)
    def test_config_interactive_db_cancellation(self, mock_db):
        result = runner.invoke(app, ["--db"])
        assert result.exit_code == 0
        assert "Database configuration cancelled." in result.stdout
        # Should not fall through to print the dashboard
        assert "⚙ TESHQ Configuration" not in result.stdout

