import sys
from typing import Optional

import typer
from sqlalchemy.exc import SQLAlchemyError

from teshq.cli import analytics, config, db, health, query, subscribe
from teshq.utils.logging import configure_global_logger
from teshq.utils.ui import handle_error
from teshq.utils.ui import info as ui_info

# from teshq.utils.ui import success, warning

app = typer.Typer(
    name="TESH Query",
    help=("A CLI tool that converts natural language queries into SQL and " "executes them on your database."),
    short_help=("A CLI tool that converts natural language queries into SQL and executes"),
    epilog="For more info, visit: https://github.com/theshashank1/TESH-Query",
)


@app.callback(invoke_without_command=True, no_args_is_help=True)
def __main__(
    version: Optional[bool] = typer.Option(False, "--version", "-v", help="Show the application's version and exit."),
    developer: Optional[bool] = typer.Option(False, "--developer", "-d", help="Show the application's author and exit."),
    log: Optional[bool] = typer.Option(
        False,
        "--log",
        help="Enable real-time logging output to CLI (logs are always saved to file).",
    ),
):
    """
    These are Global Options
    """
    configure_global_logger(enable_cli_output=log)

    if version:
        try:
            from importlib.metadata import PackageNotFoundError, version

            try:
                __version__ = version("teshq")
                print(f"teshq v{__version__}")
            except PackageNotFoundError:
                print("teshq: Unknown (Package not installed)")
        except ImportError:
            print("teshq: Unknown (importlib.metadata not available)")
        raise typer.Exit()

    if developer:
        print(
            "Developer: Shashank",
            "Linkedin: https://www.linkedin.com/in/gunda-shashank/ ",
        )
        raise typer.Exit()


app.add_typer(db.app)
app.add_typer(config.app, short_help="Configure database connection details")
app.add_typer(query.app)
app.add_typer(analytics.app, name="analytics", help="View usage analytics.")
app.add_typer(subscribe.app, name="subscribe", help="Subscribe to TESHQ updates and announcements.")
app.add_typer(health.app, name="health", help="Check system health and connectivity.")


@app.command()
def name(
    log: bool = typer.Option(
        False,
        "--log",
        help="Enable real-time logging output to CLI (logs are always saved to file).",
    ),
):
    """Show the app name."""
    configure_global_logger(enable_cli_output=log)
    from teshq.utils.logging import logger

    logger.info("Executing 'name' command")
    typer.echo(f"App Name: {app.info.name}")
    logger.info("'name' command completed successfully")


@app.command()
def help_text(
    log: bool = typer.Option(
        False,
        "--log",
        help="Enable real-time logging output to CLI (logs are always saved to file).",
    ),
):
    """Show the app help description."""
    configure_global_logger(enable_cli_output=log)
    typer.echo(f"Help: {app.info.help}")


def main():
    """Main entry point with comprehensive error handling."""
    try:
        app()
    except KeyboardInterrupt:
        ui_info("Operation cancelled by user")
        sys.exit(130)
    except typer.Abort:
        ui_info("Operation aborted")
        sys.exit(1)
    except (ImportError, ModuleNotFoundError) as e:
        handle_error(e, "Module Import", suggest_action="Ensure all dependencies are installed.")
        sys.exit(1)
    except SQLAlchemyError as e:
        handle_error(
            e,
            "Database Connection",
            suggest_action="Check config with: teshq config --interactive",
        )
        sys.exit(1)
    except FileNotFoundError as e:
        handle_error(e, "File Operation", suggest_action="Ensure all required files exist and paths are correct")
        sys.exit(1)
    except PermissionError as e:
        handle_error(e, "File Permissions", suggest_action="Check file permissions or run with appropriate privileges")
        sys.exit(1)
    except ConnectionError as e:
        handle_error(e, "Network Connection", suggest_action="Check internet connection and API credentials")
        sys.exit(1)
    except Exception as e:
        handle_error(
            e,
            "Unexpected Error",
            show_traceback=True,
            suggest_action="If this persists, please report this issue: https://github.com/theshashank1/TESH-Query/issues",
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
