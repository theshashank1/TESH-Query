import sys
from typing import Optional

import typer
from sqlalchemy.exc import SQLAlchemyError

from teshq.cli import analytics, config, db, query
from teshq.utils.logging import configure_global_logger

try:
    from teshq.cli import health
    _HEALTH_AVAILABLE = True
except ImportError:
    _HEALTH_AVAILABLE = False

try:
    from teshq.cli import subscribe
    _SUBSCRIBE_AVAILABLE = True
except ImportError:
    _SUBSCRIBE_AVAILABLE = False

try:
    from teshq.cli import telemetry as telemetry_cmd
    _TELEMETRY_CMD_AVAILABLE = True
except ImportError:
    _TELEMETRY_CMD_AVAILABLE = False

from teshq.utils.ui import handle_error
from teshq.utils.ui import info as ui_info

app = typer.Typer(
    name="teshq",
    help=(
        "TESH-Query: convert natural language into SQL and run it against your database.\n\n"
        "Quick start:\n\n"
        "  1. teshq config --db          # set up database connection\n\n"
        "  2. teshq config --gemini      # set your Gemini API key\n\n"
        "  3. teshq db introspect        # introspect the database schema\n\n"
        "  4. teshq query \"show top 10 customers by revenue\"\n\n"
        "Tips:\n\n"
        "  • Set NO_COLOR=1 to disable coloured output (CI / piped output).\n\n"
        "  • Use --log to write detailed logs to ~/.teshq/logs/ for debugging.\n"
    ),
    short_help="Natural-language SQL query tool",
    epilog="Docs & source: https://github.com/theshashank1/TESH-Query",
    no_args_is_help=True,
)


@app.callback(invoke_without_command=True)
def _callback(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", is_eager=True, help="Show version and exit."
    ),
    developer: Optional[bool] = typer.Option(
        None, "--developer", "-d", is_eager=True, help="Show developer info and exit."
    ),
    log: bool = typer.Option(
        False, "--log", help="Print log output to the terminal (always saved to file)."
    ),
):
    """TESH-Query CLI — natural language to SQL."""
    configure_global_logger(enable_cli_output=log)

    if version:
        try:
            from importlib.metadata import PackageNotFoundError, version as _ver
            try:
                __version__ = _ver("teshq")
                typer.echo(f"teshq v{__version__}")
            except PackageNotFoundError:
                typer.echo("teshq: version unknown (package not installed)")
        except ImportError:
            typer.echo("teshq: version unknown")
        raise typer.Exit()

    if developer:
        typer.echo("Developer: Shashank")
        typer.echo("LinkedIn: https://www.linkedin.com/in/gunda-shashank/")
        raise typer.Exit()



# Register sub-typers
app.add_typer(db.app, name="db", help="Manage database connections and schema introspection.")
app.add_typer(config.app, name="config", help="Configure database and API credentials.")
app.add_typer(query.app)  # already named "query" internally
app.add_typer(analytics.app, name="analytics", help="View token usage and cost analytics.")
if _HEALTH_AVAILABLE:
    app.add_typer(health.app, name="health", help="Check system health and connectivity.")
if _SUBSCRIBE_AVAILABLE:
    app.add_typer(subscribe.app, name="subscribe", help="Subscribe to TESH-Query updates.")
if _TELEMETRY_CMD_AVAILABLE:
    app.add_typer(telemetry_cmd.app, name="telemetry", help="Manage anonymous usage telemetry.")


def main():
    """Main entry point with consistent error handling."""
    try:
        app()
    except KeyboardInterrupt:
        ui_info("\nOperation cancelled.")
        sys.exit(130)
    except typer.Abort:
        ui_info("Aborted.")
        sys.exit(1)
    except (ImportError, ModuleNotFoundError) as e:
        handle_error(e, "Missing dependency", suggest_action="Run: pip install teshq[all]")
        sys.exit(1)
    except SQLAlchemyError as e:
        handle_error(
            e,
            "Database error",
            suggest_action="Check your connection with: teshq config",
        )
        sys.exit(1)
    except FileNotFoundError as e:
        handle_error(e, "File not found", suggest_action="Ensure all required files exist.")
        sys.exit(1)
    except PermissionError as e:
        handle_error(e, "Permission denied", suggest_action="Check file permissions.")
        sys.exit(1)
    except ConnectionError as e:
        handle_error(e, "Network error", suggest_action="Check internet connection and API credentials.")
        sys.exit(1)
    except Exception as e:
        handle_error(
            e,
            "Unexpected error",
            show_traceback=True,
            suggest_action="Please report this at: https://github.com/theshashank1/TESH-Query/issues",
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
