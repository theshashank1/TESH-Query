import typer

app = typer.Typer(
    name="NL2SQL CLI",
    help=(
        "A CLI tool that converts natural language queries into SQL and "
        "executes them on your database."
    ),
    short_help=(
        "A CLI tool that converts natural language queries into SQL and " "executes"
    ),
    epilog="For more info, visit: https://github.com/theshashank1/TESH-Query",
)


@app.command(name="version")
def version():
    """Show the current version."""
    typer.echo("Version: 0.1.0")


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
