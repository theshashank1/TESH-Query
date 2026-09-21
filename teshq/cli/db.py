import time
from typing import Optional
import typer
from dotenv import load_dotenv

from teshq.cli.ui import error, handle_error, print_footer, print_header, status, tip
from teshq.core.introspect import introspect_db
from teshq.telemetry.events import track_command, track_error
from teshq.cli.logging import CLILogger
from teshq.config.loader import get_database_url as get_configured_database_url

app = typer.Typer()
load_dotenv()




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
    tables_count = 0  # initialized early to avoid NameError in except/finally blocks
    
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


@app.command(name="explore", help="Display visual schema tree of tables, columns, and foreign keys.")
def explore_schema() -> None:
    """Explore introspected schema in an interactive visual tree."""
    from rich.tree import Tree
    from teshq.cli.ui.theme import Colors, Icons, console
    from teshq.core.schema_graph import SchemaGraph

    print_header("Database Schema Explorer", level=2)

    try:
        graph = SchemaGraph.from_schema_file()
        tables = graph.get_all_tables()

        if not tables:
            tip("No cached schema found. Run 'teshq db introspect' first to introspect your database.")
            raise typer.Exit(0)

        root = Tree(f"[bold {Colors.PRIMARY}]{Icons.database()} Introspected Database Schema[/bold {Colors.PRIMARY}] [dim]({len(tables)} tables)[/dim]")

        for tbl in sorted(tables):
            cols = graph.get_columns_for_table(tbl)
            fks = graph.get_foreign_keys_for_table(tbl)
            fk_map = {fk.get("constrained_column"): fk.get("referred_table") for fk in fks}

            tbl_node = root.add(f"[bold {Colors.TEXT}]{Icons.table()} {tbl}[/bold {Colors.TEXT}] [dim]({len(cols)} columns)[/dim]")

            for col in cols:
                name = col.get("name", "")
                ctype = col.get("type", "")
                is_pk = col.get("primary_key", False)

                badges = []
                if is_pk:
                    badges.append(f"[bold {Colors.WARNING}]{Icons.key()} PK[/bold {Colors.WARNING}]")
                if name in fk_map:
                    badges.append(f"[bold {Colors.SECONDARY}]{Icons.link()} FK ➔ {fk_map[name]}[/bold {Colors.SECONDARY}]")

                badge_str = f"  {' '.join(badges)}" if badges else ""
                tbl_node.add(f"[dim {Colors.MUTED}]{name}[/dim {Colors.MUTED}] [dim]({ctype})[/dim]{badge_str}")

        console.print(root)
        console.print()

    except Exception as e:
        handle_error(e, "Schema Explorer", suggest_action="Run 'teshq db introspect' to refresh your schema.")
        raise typer.Exit(1)


@app.command(name="preview", help="Preview sample rows from any table.")
def preview_table(
    table_name: str = typer.Argument(..., help="Name of the table to preview."),
    limit: int = typer.Option(5, "--limit", "-n", help="Number of rows to preview."),
) -> None:
    """Preview sample rows from a specific database table."""
    from teshq.cli.ui import print_results_table, error, success
    from teshq.core.engine import TeshEngine

    try:
        engine = TeshEngine()
        query = f"SELECT * FROM {table_name} LIMIT {limit};"
        
        with status(f"Fetching sample data from {table_name}..."):
            rows = engine.connection.execute_query(query)

        if not rows:
            tip(f"Table '{table_name}' contains 0 rows.")
            raise typer.Exit(0)

        headers = list(rows[0].keys())
        data = [[row[h] for h in headers] for row in rows]

        print_results_table(
            headers=headers,
            rows=data,
            title=f"Sample Preview: {table_name}",
            summary=f"Showing {len(rows)} sample record(s)",
        )
    except Exception as e:
        handle_error(e, f"Table Preview ({table_name})", suggest_action=f"Verify table '{table_name}' exists using 'teshq db explore'")
        raise typer.Exit(1)


# Register alias for explore
app.command(name="tree", help="Alias for 'teshq db explore'")(explore_schema)


if __name__ == "__main__":
    app()
    print_footer()
