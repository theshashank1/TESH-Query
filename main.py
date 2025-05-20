from typing import Optional

import typer

app = typer.Typer(
    name="TESH Query",
    help=(
        "A CLI tool that converts natural language queries into SQL and "
        "executes them on your database."
    ),
    short_help=(
        "A CLI tool that converts natural language queries into SQL and executes"
    ),
    epilog="For more info, visit: https://github.com/theshashank1/TESH-Query",
)


@app.callback(invoke_without_command=True)
def __main__(
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", help="Show the application's version and exit."
    ),
    author: Optional[bool] = typer.Option(
        None, "--author", "-a", help="Show the application's author and exit."
    ),
):
    if version:
        print("version 0.1.0")
        raise typer.Exit()

    if author:
        print("Author: Shashank")
        raise typer.Exit()


@app.command()
def name():
    """Show the app name."""
    typer.echo(f"App Name: {app.info.name}")


@app.command()
def help_text():
    """Show the app help description."""
    typer.echo(f"Help: {app.info.help}")


if __name__ == "__main__":
    app()
