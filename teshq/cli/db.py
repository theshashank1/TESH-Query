import typer
from dotenv import load_dotenv

from teshq.cli.ui import error, handle_error, print_footer, print_header, status, tip, warning
from teshq.core.db import connect_database, disconnect_database
from teshq.core.introspect import introspect_db
from teshq.utils.config import get_database_url as get_configured_database_url

app = typer.Typer(
    name="teshq",
    help="TESH-Query: Convert natural language to SQL queries.",
    add_completion=False,
)
load_dotenv()


@app.command()
def database(
    connect: bool = typer.Option(False, "--connect", help="Connect to the database"),
    disconnect: bool = typer.Option(False, "--disconnect", help="Disconnect from the database (after connection)"),
):
    """
    Manage database connection lifecycle: connect and optionally disconnect.
    """
    print_header("Database Connection Manager", level=2)

    db_url = get_configured_database_url()

    if not db_url:
        error("DATABASE_URL not set in environment variables or config.json.")
        raise typer.Exit(code=1)
    conn = None
    if connect:
        try:
            with status(
                "Connecting to the database...",
                success_message="Database connection successful.",
            ):
                conn = connect_database(db_url)
        except Exception as e:
            handle_error(
                e,
                "Database Connection",
                suggest_action="Please check your DATABASE_URL and network settings.",
            )
            raise typer.Exit(code=1)

        if disconnect:
            try:
                with status(
                    "Disconnecting from database...",
                    success_message="Database disconnection successful.",
                ):
                    disconnect_database(conn)
            except Exception as e:
                handle_error(e, "Database Disconnection")

    elif disconnect and not connect:
        warning("Cannot disconnect without an active connection. Use --connect.")

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
        help="Detect implicit relationships from naming conventions.",
    ),
):
    """
    Perform database schema introspection optimized for LLM query generation.
    """
    print_header("Database Schema Introspection", level=2)
    try:  # Introspection logic handles db_url if None
        with status(
            "Performing database introspection...",
            success_message="Introspection complete.",
        ):
            # introspect_db will handle finding the db_url if not provided
            introspect_db(db_url=db_url, detect_relationships=detect_relationships)
        tip("Schema details have been processed and are ready for use.")
    except Exception as e:
        handle_error(
            e,
            "Database Introspection",
            suggest_action="Ensure the database is accessible and the schema is valid.",
        )
        raise typer.Exit(code=1)


if __name__ == "__main__":
    # This script runs as a Typer CLI application.
    # Execute `python -m teshq.cli.main --help` to see commands.
    app()
print_footer()
