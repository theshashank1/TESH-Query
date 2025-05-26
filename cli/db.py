import json
import os

import typer
from dotenv import load_dotenv
from sqlalchemy import text

from core.db import connect_database, disconnect_database
from core.introspect import introspect_db

app = typer.Typer()
load_dotenv()


@app.command()
def database(
    connect: bool = typer.Option(False, "--connect", help="Connect to the database"),
    disconnect: bool = typer.Option(False, "--disconnect", help="Disconnect from the database (after connection)"),
):
    """
    Manage database connection lifecycle: connect and optionally disconnect.
    """

    db_url = os.getenv("DATABASE_URL")

    # Fallback to config.json if not found in .env
    if not db_url:
        try:
            with open("config.json", "r") as f:
                config_data = json.load(f)
                db_url = config_data.get("DATABASE_URL")
                if db_url:
                    typer.secho("Using DATABASE_URL from config.json", fg=typer.colors.CYAN)
                else:
                    typer.secho("DATABASE_URL not found in config.json.", fg=typer.colors.RED)
        except FileNotFoundError:
            typer.secho("Error: config.json not found.", fg=typer.colors.RED)
        except json.JSONDecodeError:
            typer.secho("Error: config.json is not a valid JSON file.", fg=typer.colors.RED)

    if not db_url:
        typer.secho(
            "DATABASE_URL not set in either environment variables or config.json.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    conn = None

    if connect:
        typer.secho("Connecting to the database...", fg=typer.colors.YELLOW)
        try:
            conn = connect_database(db_url)
            typer.secho("✅ Connected to the database.", fg=typer.colors.GREEN)
        except Exception as e:
            typer.secho(f"Failed to connect: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        if disconnect:
            typer.secho("Disconnecting...", fg=typer.colors.YELLOW)
            try:
                disconnect_database(conn)
                typer.secho("✅ Disconnected from the database.", fg=typer.colors.GREEN)
            except Exception as e:
                typer.secho(f"Error while disconnecting: {e}", fg=typer.colors.RED)

    elif disconnect and not connect:
        typer.secho("Cannot disconnect without connecting first.", fg=typer.colors.RED)

    return conn


@app.command()
def introspect(
    db_url: str = typer.Option(
        None,
        "--db-url",
        help="Full database URL (e.g. postgresql://user:pass@host:port/dbname)",
    ),
    detect_relationships: bool = typer.Option(
        True,
        "--detect-relationships",
        "-r",
        help="Whether to detect implicit relationships based on naming conventions",
    ),
):
    """
    Perform database schema introspection optimized for LLM query generation.
    """

    if db_url:
        introspect_db(db_url=db_url, detect_relationships=detect_relationships)

    if not db_url:
        introspect_db()


if __name__ == "__main__":
    conn = connect_database
    conn.executes(text("SELECT * FROM employees;"))
    disconnect_database(conn)
    app()
