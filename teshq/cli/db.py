import time
from typing import Optional
import typer
from dotenv import load_dotenv

from teshq.cli.ui import error, handle_error, print_footer, print_header, status, tip, warning
from teshq.core.introspect import introspect_db
from teshq.telemetry.events import track_command, track_error
from teshq.cli.logging import CLILogger
from teshq.config.loader import get_database_url as get_configured_database_url
from teshq.core.connection import connection_manager

app = typer.Typer()
load_dotenv()


@app.command()
def database(
    connect: bool = typer.Option(False, "--connect", help="Connect to the database"),
    disconnect: bool = typer.Option(False, "--disconnect", help="Disconnect from the database (after connection)"),
):
    """
    Manage the database connection lifecycle for the CLI command.
    
    Connects to the configured database when `connect` is true and optionally disconnects immediately when `disconnect` is also true. Exits the process with a non-zero code if no database URL is configured or if a connection attempt fails.
    
    Parameters:
        connect (bool): If true, establish a database connection.
        disconnect (bool): If true and `connect` is also true, disconnect after a successful connection; has no effect otherwise.
    
    Returns:
        Connection object if a connection was established, `None` otherwise.
    """
    print_header("Database Connection Manager", level=2)

    db_url = get_configured_database_url()

    if not db_url:
        error("DATABASE_URL not set. Configure it with: teshq config --db")
        raise typer.Exit(code=1)
    conn = None
    if connect:
        try:
            with status(
                    "Connecting to the database...",
                    success_message="Database connection successful.",
                ):
                    conn = connection_manager.get_engine(db_url)
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
                    conn.dispose()
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
    full_schema: bool = typer.Option(
        False,
        "--all",
        help="Also save full verbose schema (schema_full.txt) with row counts, indexes, and inferred relationships.",
    ),
    log: bool = typer.Option(None, "--log", help="Enable logging to file (overrides config default)"),
):
    """
    Perform database schema introspection optimized for LLM query generation.
    """
    
    # Initialize CLI logger
    cli_logger = CLILogger("introspect")
    logging_active = cli_logger.setup_file_logging(log)
    
    start_time = time.time()
    
    try:
        print_header("Database Schema Introspection", level=2)
        
        # Log command start
        if logging_active:
            cli_logger.log_command_start({
                "db_url": "***" if db_url else None,  # Hide sensitive URL
                "detect_relationships": detect_relationships,
                "log": log
            })
        
        schema_mode = "full" if full_schema else "minimal"

        # Introspection logic handles db_url if None
        with status(
            "Performing database introspection...",
            success_message="Introspection complete.",
        ):
            # introspect_db will handle finding the db_url if not provided
            result = introspect_db(
                db_url=db_url,
                detect_relationships=detect_relationships,
                include_indexes=full_schema,  # Only collect indexes when --all is set
                schema_mode=schema_mode,
            )

        if logging_active:
            # Log introspection results
            tables_count = len(result.get("tables", {})) if result else 0
            cli_logger.log_info("Database introspection completed",
                                tables_count=tables_count,
                                detect_relationships=detect_relationships)

        
        if full_schema:
            tip("Schema saved: schema.txt (compact, default) + schema_full.txt (full detail with indexes & row counts).")
        else:
            tip("Schema saved: schema.txt (compact, token-efficient). Use --all to also save full detail schema.")
        
        # Log successful completion
        if logging_active:
            duration = time.time() - start_time
            cli_logger.log_command_end(True, duration, tables_count=tables_count)
            
    except Exception as e:
        if logging_active:
            duration = time.time() - start_time
            cli_logger.log_command_end(False, duration, error=str(e), error_type=type(e).__name__)
        
        handle_error(
            e,
            "Database Introspection",
            suggest_action="Ensure the database is accessible and the schema is valid.",
        )
        raise typer.Exit(code=1)
    finally:
        # Cleanup logger
        if logging_active:
            cli_logger.cleanup()


if __name__ == "__main__":
    # This script runs as a Typer CLI application.
    # Execute `python -m teshq.cli.main --help` to see commands.
    app()
    print_footer()
