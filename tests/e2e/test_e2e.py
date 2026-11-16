"""
End-to-End (E2E) CLI workflow tests for TESH-Query.

Validates the top-level CLI application, subcommands, options, and help outputs.
"""

import pytest
from typer.testing import CliRunner

from teshq.cli.main import app

runner = CliRunner()


def test_cli_version():
    """Verify `teshq --version` displays the current version."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "teshq v" in result.output.lower() or "version" in result.output.lower()


def test_cli_developer():
    """Verify `teshq --developer` shows developer info."""
    result = runner.invoke(app, ["--developer"])
    assert result.exit_code == 0
    assert "developer:" in result.output.lower()
    assert "shashank" in result.output.lower()


def test_cli_root_help():
    """Verify `teshq --help` contains core command listings."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    output = result.output.lower()
    assert "query" in output
    assert "config" in output
    assert "db" in output


@pytest.mark.parametrize(
    "subcommand",
    [
        "query",
        "config",
        "db",
        "analytics",
        "chat",
        "bench",
        "model",
    ],
)
def test_subcommand_help_screens(subcommand):
    """Verify each primary subcommand provides a working `--help` screen."""
    result = runner.invoke(app, [subcommand, "--help"])
    assert result.exit_code == 0
    assert "usage:" in result.output.lower() or subcommand in result.output.lower()
