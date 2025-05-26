import importlib.metadata
from typing import Optional

import typer

from cli import config, db, query

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
            __version__ = importlib.metadata.version("tesh-query")
            print(f"TESH Query Version: {__version__}")
        except importlib.metadata.PackageNotFoundError:
            print("TESH Query Version: Unknown (Package not installed)")
        raise typer.Exit()

    if developer:
        print("Developer: Shashank")
        raise typer.Exit()


app.add_typer(config.app, short_help="Configure database connection details")
app.add_typer(db.app)
app.add_typer(query.app)


@app.command()
def name():
    """Show the app name."""
    typer.echo(f"App Name: {app.info.name}")


@app.command()
def help_text():
    """Show the app help description."""
    typer.echo(f"Help: {app.info.help}")


if __name__ == "__main__":
    try:
        app()
    except Exception as e:
        typer.echo(f"An unexpected error occurred: {e}", err=True)
