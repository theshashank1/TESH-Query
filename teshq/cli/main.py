import sys
import warnings

# ──────────────────────────────────────────────────────────────────────────────
# Suppress LangChain / Pydantic V1 compatibility warnings on Python 3.14+.
# These come from langchain_core internals and are not actionable by users.
# We suppress them at the earliest possible point — before any langchain import.
# ──────────────────────────────────────────────────────────────────────────────
warnings.filterwarnings(
    "ignore",
    message=r".*Pydantic V1 functionality.*",
    category=UserWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r".*pydantic.v1.*",
    category=UserWarning,
)

from typing import Optional

import typer
from sqlalchemy.exc import SQLAlchemyError

from teshq.cli import analytics, config, db, query, local, bench, model, chat
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

from teshq.cli.ui import handle_error
from teshq.cli.ui import info as ui_info

app = typer.Typer(
    name="teshq",
    help=(
        "TESH-Query: Autonomous Natural Language SQL Exploration Engine.\n\n"
        "Quick start:\n\n"
        "  1. teshq chat                 # launch interactive natural language terminal\n\n"
        "  2. teshq query \"your question\" # run single natural language query\n\n"
        "  3. teshq db explore           # view database schema in a visual tree\n\n"
        "  4. teshq config --db          # configure database connection URL\n\n"
        "Tips:\n\n"
        "  • Use 'teshq chat' for conversational follow-ups and slash commands.\n\n"
        "  • Set NO_COLOR=1 to disable coloured output (CI / piped output).\n\n"
        "  • Use --verbose to write detailed logs to ~/.teshq/logs/ for debugging.\n"
    ),
    short_help="Autonomous Natural Language SQL Engine",
    epilog="Docs & source: https://github.com/theshashank1/TESH-Query",
    no_args_is_help=False,
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
    verbose: bool = typer.Option(
        False, "--verbose", help="Write detailed logs to ~/.teshq/logs/ for debugging."
    ),
):
    """TESH-Query CLI — autonomous natural language to SQL."""
    configure_global_logger(enable_cli_output=verbose)

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

    # If invoked with no subcommand, show minimal welcome
    if ctx.invoked_subcommand is None:
        from teshq.cli.ui.banner import print_hero_banner, print_hud
        from teshq.cli.chat import _get_env_summary
        from teshq.cli.ui.theme import console, Colors, Icons
        from rich.text import Text

        print_hero_banner()
        db_status, db_type, llm_name, table_count = _get_env_summary()
        print_hud(db_status=db_status, db_type=db_type, llm_model=llm_name, schema_tables_count=table_count)
        console.print()

        # Clean command list — no panels, no borders
        commands = [
            ("teshq chat",              "Interactive conversational terminal"),
            ('teshq query "..."',       "Single natural language query"),
            ("teshq db explore",        "Explore database schema"),
            ("teshq config --db",       "Configure database connection"),
            ("teshq --help",            "All commands and options"),
        ]

        console.print(f"  [{Colors.TEXT_TERTIARY}]Get started:[/{Colors.TEXT_TERTIARY}]")
        for cmd, desc in commands:
            console.print(
                f"    [{Colors.PRIMARY}]{cmd:<28s}[/{Colors.PRIMARY}]"
                f"[{Colors.TEXT_MUTED}]{desc}[/{Colors.TEXT_MUTED}]"
            )

        console.print()
        console.print(
            f"  [{Colors.TEXT_TERTIARY}]Try:[/{Colors.TEXT_TERTIARY}]"
        )
        console.print(
            f"    [{Colors.PRIMARY}]{Icons.prompt()}[/{Colors.PRIMARY}] "
            f"[italic {Colors.TEXT_SECONDARY}]teshq query "
            f"\"show top 5 customers by revenue\""
            f"[/italic {Colors.TEXT_SECONDARY}]"
        )
        console.print()
        raise typer.Exit()


# Register sub-typers
app.add_typer(chat.app, name="chat", help="Launch interactive multi-turn SQL chat session.")
app.add_typer(chat.app, name="repl", help="Alias for 'teshq chat'.")
app.add_typer(db.app, name="db", help="Manage database connections and schema introspection.")
app.add_typer(config.app, name="config", help="Configure database and API credentials.")
app.add_typer(query.app)  # already named "query" internally
app.add_typer(local.app, name="local")
app.add_typer(bench.app, name="bench", help="Run text-to-SQL benchmarks against backends.")
app.add_typer(model.app, name="model", help="Manage local GGUF models and downloads.")

app.add_typer(analytics.app, name="analytics", help="View token usage and cost analytics.")
if _HEALTH_AVAILABLE:
    app.add_typer(health.app, name="health", help="Check system health and connectivity.")
if _SUBSCRIBE_AVAILABLE:
    app.add_typer(subscribe.app, name="subscribe", help="Subscribe to TESH-Query updates.")
if _TELEMETRY_CMD_AVAILABLE:
    app.add_typer(telemetry_cmd.app, name="telemetry", help="Manage anonymous usage telemetry.")

# Register top-level aliases
from teshq.cli.db import introspect as introspect_cmd
app.command(name="introspect", help="Perform database schema introspection (alias for `db introspect`)")(introspect_cmd)


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
