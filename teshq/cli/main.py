import importlib.metadata
import sys
from typing import Optional

import typer
from sqlalchemy.exc import SQLAlchemyError

from teshq.cli import config, db, query

# from teshq.utils.ui import error as ui_error
from teshq.utils.ui import handle_error
from teshq.utils.ui import info as ui_info

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
):
    """
    These are Global Options
    """
    if version:
        try:
            from importlib.metadata import PackageNotFoundError, version

            try:
                __version__ = version("teshq")
                base_version = __version__
                print(f"teshq v{base_version}")
            except PackageNotFoundError:
                __version__ = "unknown"

            # base_version = __version__.split(".dev")[0]
            # print(f"teshq v{base_version}")
        except importlib.metadata.PackageNotFoundError:
            print("teshq: Unknown (Package not installed)")
        raise typer.Exit()

    if developer:
        print("Developer: Shashank", "Linkedin: https://www.linkedin.com/in/gunda-shashank/ ")
        raise typer.Exit()


app.add_typer(db.app)
app.add_typer(config.app, short_help="Configure database connection details")
app.add_typer(query.app)


@app.command()
def name():
    """Show the app name."""
    typer.echo(f"App Name: {app.info.name}")


@app.command()
def help_text():
    """Show the app help description."""
    typer.echo(f"Help: {app.info.help}")


def main():
    """Main entry point with comprehensive error handling."""
    try:
        app()
    except KeyboardInterrupt:
        ui_info("Operation cancelled by user")
        sys.exit(130)  # Standard exit code for Ctrl+C
    except typer.Abort:
        ui_info("Operation aborted")
        sys.exit(1)
    except ImportError as e:
        handle_error(e, "Module Import", suggest_action="Ensure all dependencies are installed with: pip install -e .")
        sys.exit(1)
    except SQLAlchemyError as e:
        handle_error(
            e, "Database Connection", suggest_action="Check your database configuration with: teshq config --interactive"
        )
        sys.exit(1)
    except FileNotFoundError as e:
        handle_error(e, "File Operation", suggest_action="Ensure all required files exist and paths are correct")
        sys.exit(1)
    except PermissionError as e:
        handle_error(e, "File Permissions", suggest_action="Check file permissions or run with appropriate privileges")
        sys.exit(1)
    except ConnectionError as e:
        handle_error(e, "Network Connection", suggest_action="Check your internet connection and API credentials")
        sys.exit(1)
    except Exception as e:
        handle_error(
            e,
            "Unexpected Error",
            show_traceback=True,
            suggest_action="If this persists, please report this issue at:https://github.com/theshashank1/TESH-Query/issues",
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
