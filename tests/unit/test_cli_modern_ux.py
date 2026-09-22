"""
Unit tests for modernized CLI UX across query, health, analytics, subscribe, and db commands.

Verifies:
  - Rich help panel grouping
  - Machine-readable --json support for automation/CI
  - Default HUD/summary display on invoke without command
  - Clean cancellation exits (exit code 0, no unhandled exceptions)
  - Relative paths and masking
"""

import json
from unittest.mock import MagicMock, patch
from typer.testing import CliRunner

from teshq.cli.health import app as health_app
from teshq.cli.analytics import app as analytics_app
from teshq.cli.subscribe import app as subscribe_app
from teshq.cli.db import app as db_app
from teshq.cli.query import app as query_app

runner = CliRunner()


class TestHealthCLIUX:
    """Tests for modernized teshq health CLI."""

    def test_health_help_panels(self):
        result = runner.invoke(health_app, ["--help"])
        assert result.exit_code == 0
        assert "⚙️ Diagnostics & Output" in result.stdout
        assert "--json" in result.stdout
        assert "--verbose" in result.stdout

    @patch("teshq.cli.health.HealthChecker")
    def test_health_json_output(self, mock_checker_cls):
        mock_instance = MagicMock()
        mock_instance.run_all_checks.return_value = {
            "status": "healthy",
            "duration_ms": 12.5,
            "checks": [
                {"name": "database_connectivity", "status": "healthy", "duration_ms": 5.0, "message": "OK"}
            ],
            "summary": {"total_checks": 1, "status_breakdown": {"healthy": 1}},
        }
        mock_checker_cls.return_value = mock_instance

        result = runner.invoke(health_app, ["--json"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert parsed["status"] == "healthy"
        assert len(parsed["checks"]) == 1

    @patch("teshq.cli.health.HealthChecker")
    def test_health_cancellation(self, mock_checker_cls):
        mock_instance = MagicMock()
        mock_instance.run_all_checks.side_effect = KeyboardInterrupt
        mock_checker_cls.return_value = mock_instance

        result = runner.invoke(health_app, [])
        assert result.exit_code == 0
        assert "Operation cancelled." in result.stdout


class TestAnalyticsCLIUX:
    """Tests for modernized teshq analytics CLI."""

    def test_analytics_default_invokes_summary(self):
        with patch("teshq.cli.analytics.get_summary") as mock_summary:
            mock_summary.return_value = {
                "first_seen": "2026-01-01",
                "last_seen": "2026-02-01",
                "total_queries": 10,
                "successful_queries": 9,
                "failed_queries": 1,
                "total_tokens": 1000,
                "prompt_tokens": 600,
                "completion_tokens": 400,
                "estimated_cost_usd": 0.05,
                "avg_latency_ms": 120.0,
                "total_commands": 15,
                "provider_breakdown": {"azure": 10},
                "command_breakdown": {"query": 10},
            }
            result = runner.invoke(analytics_app, [])
            assert result.exit_code == 0
            assert "Local Usage & Token Analytics" in result.stdout
            assert "Total Queries:" in result.stdout

    def test_analytics_show_json(self):
        with patch("teshq.cli.analytics.get_summary") as mock_summary:
            mock_summary.return_value = {
                "total_queries": 42,
                "successful_queries": 40,
                "failed_queries": 2,
                "total_tokens": 5000,
                "prompt_tokens": 3000,
                "completion_tokens": 2000,
                "estimated_cost_usd": 0.12,
                "avg_latency_ms": 250.0,
                "total_commands": 50,
            }
            result = runner.invoke(analytics_app, ["show", "--json"])
            assert result.exit_code == 0
            parsed = json.loads(result.stdout)
            assert parsed["total_queries"] == 42

    def test_analytics_reset_interactive_cancel(self):
        with patch("teshq.cli.analytics.Confirm.ask", return_value=False):
            result = runner.invoke(analytics_app, ["reset"])
            assert result.exit_code == 0
            assert "cancelled" in result.stdout.lower()

    @patch("teshq.cli.analytics.reset_metrics", return_value=True)
    def test_analytics_reset_non_interactive(self, mock_reset):
        result = runner.invoke(analytics_app, ["reset", "--yes"])
        assert result.exit_code == 0
        assert "Local metrics have been reset" in result.stdout
        mock_reset.assert_called_once()


class TestSubscribeCLIUX:
    """Tests for modernized teshq subscribe CLI."""

    def test_subscribe_help_panels(self):
        result = runner.invoke(subscribe_app, ["--help"])
        assert result.exit_code == 0
        assert "✨ Subscriber Details" in result.stdout
        assert "⚙️ Automation & Scripting" in result.stdout
        assert "--name" in result.stdout
        assert "--email" in result.stdout
        assert "--yes" in result.stdout

    @patch("teshq.cli.subscribe.prompt", side_effect=KeyboardInterrupt)
    def test_subscribe_interactive_cancel(self, mock_prompt):
        result = runner.invoke(subscribe_app, [])
        assert result.exit_code == 0
        assert "Subscription cancelled." in result.stdout


class TestDbCLIUX:
    """Tests for modernized teshq db CLI."""

    def test_db_default_hud(self):
        with patch("teshq.cli.db.get_configured_database_url", return_value="sqlite:///test.sqlite"):
            result = runner.invoke(db_app, [])
            assert result.exit_code == 0
            assert "Database Management HUD" in result.stdout
            assert "sqlite:///test.sqlite" in result.stdout
            assert "teshq db explore" in result.stdout

    def test_db_introspect_help_panels(self):
        result = runner.invoke(db_app, ["introspect", "--help"])
        assert result.exit_code == 0
        assert "🗄️ Database Connection" in result.stdout
        assert "🔍 Introspection Controls" in result.stdout
        assert "⚙️ Diagnostics" in result.stdout
        assert "--detect-relationships" in result.stdout
        assert "--all" in result.stdout

    def test_db_preview_help_panels(self):
        result = runner.invoke(db_app, ["preview", "--help"])
        assert result.exit_code == 0
        assert "📑 Preview Options" in result.stdout
        assert "--limit" in result.stdout

    def test_db_explore_renders_tree(self):
        result = runner.invoke(db_app, ["explore"])
        assert result.exit_code == 0
        assert "Introspected Database Schema" in result.stdout


class TestModelCLIUX:
    """Tests for modernized teshq model CLI."""

    def test_model_default_invokes_list(self):
        from teshq.cli.model import app as model_app

        result = runner.invoke(model_app, [])
        assert result.exit_code == 0
        assert "Local GGUF Models" in result.stdout
        assert "Registry Models Available" in result.stdout

    def test_model_list_json(self):
        from teshq.cli.model import app as model_app

        result = runner.invoke(model_app, ["list", "--json"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert "installed" in parsed
        assert "registry" in parsed
        assert len(parsed["registry"]) > 0


class TestLocalCLIUX:
    """Tests for modernized teshq local CLI."""

    def test_local_default_invokes_status(self):
        from teshq.cli.local import app as local_app

        result = runner.invoke(local_app, [])
        assert result.exit_code == 0
        assert "Local Inference Engine HUD" in result.stdout
        assert "Host Hardware" in result.stdout

    def test_local_status_json(self):
        from teshq.cli.local import app as local_app

        result = runner.invoke(local_app, ["status", "--json"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert "hardware" in parsed
        assert "cpu_cores" in parsed["hardware"]
        assert "configured_model" in parsed


class TestQueryCLIUX:
    """Tests for modernized teshq query CLI."""

    def test_query_help_panels(self):
        result = runner.invoke(query_app, ["--help"])
        assert result.exit_code == 0
        assert "📤 Export & Output Files" in result.stdout
        assert "⚡ Execution & Query Controls" in result.stdout
        assert "🤖 Model & Inference Routing" in result.stdout
        assert "⚙️ Diagnostics & Logging" in result.stdout
        assert "--save-csv" in result.stdout
        assert "--dry-run" in result.stdout
        assert "--limit" in result.stdout
