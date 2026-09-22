import os
import time
from typing import Optional
import typer
from dotenv import load_dotenv
from sqlalchemy.engine import make_url

from teshq.cli.ui import handle_error, print_header, status, tip
from teshq.cli.ui.theme import Colors, Icons, ROUNDED_BOX, console
from teshq.core.introspect import introspect_db
from teshq.cli.logging import CLILogger
from teshq.config.loader import get_database_url as get_configured_database_url

app = typer.Typer(
    name="db",
    help="Manage database connections, schema introspection, and table previews.",
    invoke_without_command=True,
)
load_dotenv()

PANEL_DB = "🗄️ Database Connection"
PANEL_INTROSPECT = "🔍 Introspection Controls"
PANEL_PREVIEW = "📑 Preview Options"
PANEL_DIAGNOSTICS = "⚙️ Diagnostics"


def display_db_dashboard() -> None:
    """Render a clean database connection and schema status HUD."""
    from rich.panel import Panel
    from teshq.core.schema_graph import SchemaGraph

    db_url = get_configured_database_url()
    if db_url:
        try:
            url_obj = make_url(db_url)
            backend = (url_obj.get_backend_name() or "database").lower()
            if backend == "sqlite":
                db_path = url_obj.database or ""
                try:
                    rel_path = os.path.relpath(db_path, os.getcwd())
                    display_path = rel_path if not rel_path.startswith("..") else os.path.basename(db_path)
                except Exception:
                    display_path = os.path.basename(db_path) or db_path
                display_path = display_path.replace("\\", "/")
                masked = f"sqlite:///{display_path}"
                db_status = f"[bold {Colors.SUCCESS}]● Connected[/bold {Colors.SUCCESS}]"
                db_detail = f"[{Colors.TEXT_PRIMARY}]{masked}[/{Colors.TEXT_PRIMARY}]"
            else:
                db_name = url_obj.database or "—"
                host = url_obj.host or "localhost"
                port_str = f":{url_obj.port}" if url_obj.port else ""
                user_str = f"{url_obj.username}@" if url_obj.username else ""
                masked = f"{backend}://{user_str}*****@{host}{port_str}/{db_name}" if url_obj.username else f"{backend}://{host}{port_str}/{db_name}"
                db_status = f"[bold {Colors.SUCCESS}]● Connected[/bold {Colors.SUCCESS}]"
                db_detail = f"[{Colors.TEXT_PRIMARY}]{masked}[/{Colors.TEXT_PRIMARY}]"
        except Exception:
            db_status = f"[bold {Colors.WARNING}]● Configured[/bold {Colors.WARNING}]"
            db_detail = f"[{Colors.TEXT_MUTED}](URL set but could not parse)[/{Colors.TEXT_MUTED}]"
    else:
        db_status = f"[bold {Colors.ERROR}]● Not Configured[/bold {Colors.ERROR}]"
        db_detail = f"[{Colors.TEXT_MUTED}]Run 'teshq config --db' to connect[/{Colors.TEXT_MUTED}]"

    try:
        graph = SchemaGraph.from_schema_file()
        tables = graph.get_all_tables()
        table_count = len(tables)
        if table_count > 0:
            schema_info = f"[bold {Colors.SUCCESS}]{table_count} tables[/bold {Colors.SUCCESS}] cached and ready"
        else:
            schema_info = f"[{Colors.WARNING}]No cached schema found (run 'teshq db introspect')[/{Colors.WARNING}]"
    except Exception:
        schema_info = f"[{Colors.WARNING}]No cached schema found (run 'teshq db introspect')[/{Colors.WARNING}]"

    hud_text = f"""[{Colors.TEXT_TERTIARY}]Connection Status:[/{Colors.TEXT_TERTIARY}] {db_status}
[{Colors.TEXT_TERTIARY}]Database URL:[/{Colors.TEXT_TERTIARY}]      {db_detail}
[{Colors.TEXT_TERTIARY}]Introspected Schema:[/{Colors.TEXT_TERTIARY}] {schema_info}

[{Colors.TEXT_TERTIARY}]Available Commands:[/{Colors.TEXT_TERTIARY}]
  [{Colors.PRIMARY}]teshq db explore[/{Colors.PRIMARY}]          [{Colors.TEXT_SECONDARY}]Display visual interactive schema tree[/{Colors.TEXT_SECONDARY}]
  [{Colors.PRIMARY}]teshq db introspect[/{Colors.PRIMARY}]       [{Colors.TEXT_SECONDARY}]Re-run schema introspection & relationship inference[/{Colors.TEXT_SECONDARY}]
  [{Colors.PRIMARY}]teshq db preview <table-name>[/{Colors.PRIMARY}] [{Colors.TEXT_SECONDARY}]Preview sample records from any table[/{Colors.TEXT_SECONDARY}]
  [{Colors.PRIMARY}]teshq config --db[/{Colors.PRIMARY}]         [{Colors.TEXT_SECONDARY}]Configure or switch database connection URL[/{Colors.TEXT_SECONDARY}]"""

    console.print(
        Panel(
            hud_text,
            title=f"[bold {Colors.PRIMARY}]{Icons.database()} Database Management HUD[/bold {Colors.PRIMARY}]",
            box=ROUNDED_BOX,
            border_style=Colors.BORDER_DEFAULT,
            expand=False,
        )
    )


@app.callback(invoke_without_command=True)
def db_default(ctx: typer.Context):
    """Database management and schema exploration HUD."""
    if ctx.invoked_subcommand is None:
        display_db_dashboard()


@app.command()
def introspect(
    db_url: str = typer.Option(
        None,
        "--db-url",
        help="Full database URL (e.g. postgresql://user:pass@host:port/dbname).",
        rich_help_panel=PANEL_DB,
    ),
    detect_relationships: bool = typer.Option(
        True,
        "--detect-relationships",
        "-r",
        help="Detect implicit relationships from naming conventions and foreign keys.",
        rich_help_panel=PANEL_INTROSPECT,
    ),
    full_schema: bool = typer.Option(
        False,
        "--all",
        help="Also save full verbose schema (schema_full.txt) with row counts, indexes, and inferred relationships.",
        rich_help_panel=PANEL_INTROSPECT,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging and diagnostics.",
        rich_help_panel=PANEL_DIAGNOSTICS,
    ),
):
    """
    Perform database schema introspection optimized for LLM query generation.
    """
    # Initialize CLI logger
    cli_logger = CLILogger("introspect")
    logging_active = cli_logger.setup_file_logging(verbose)

    start_time = time.time()
    tables_count = 0

    try:
        print_header("Database Schema Introspection", level=2)

        if logging_active:
            cli_logger.log_command_start({
                "db_url": "***" if db_url else None,
                "detect_relationships": detect_relationships,
                "verbose": verbose,
            })

        schema_mode = "full" if full_schema else "minimal"

        with status(
            "Performing database introspection...",
            success_message="Introspection complete.",
        ):
            result = introspect_db(
                db_url=db_url,
                detect_relationships=detect_relationships,
                include_indexes=full_schema,
                schema_mode=schema_mode,
            )

        if logging_active:
            tables_count = len(result.get("tables", {})) if result else 0
            cli_logger.log_info(
                "Database introspection completed",
                tables_count=tables_count,
                detect_relationships=detect_relationships,
            )

        if full_schema:
            tip("Schema saved: schema.txt (compact, default) + schema_full.txt (full detail with indexes & row counts).")
        else:
            tip("Schema saved: schema.txt (compact, token-efficient). Use --all to also save full detail schema.")

        if logging_active:
            duration = time.time() - start_time
            cli_logger.log_command_end(True, duration, tables_count=tables_count)

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        if logging_active:
            duration = time.time() - start_time
            cli_logger.log_command_end(False, duration, error="Cancelled by user", error_type="KeyboardInterrupt")
        console.print(f"\n[{Colors.TEXT_MUTED}]Operation cancelled.[/{Colors.TEXT_MUTED}]")
        raise typer.Exit(0)
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
        if logging_active:
            cli_logger.cleanup()


@app.command(name="explore", help="Display visual schema tree of tables, columns, and foreign keys.")
def explore_schema() -> None:
    """Explore introspected schema in an interactive visual tree."""
    from rich.tree import Tree
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

            tbl_node = root.add(f"[bold {Colors.TEXT_PRIMARY}]{Icons.table()} {tbl}[/bold {Colors.TEXT_PRIMARY}] [dim]({len(cols)} columns)[/dim]")

            for col in cols:
                name = col.get("name", "")
                ctype = col.get("type", "")
                is_pk = col.get("primary_key", False)

                badges = []
                if is_pk:
                    badges.append(f"[bold {Colors.WARNING}]{Icons.key()} PK[/bold {Colors.WARNING}]")
                if name in fk_map:
                    badges.append(f"[bold {Colors.AI_ACCENT}]{Icons.link()} FK ➔ {fk_map[name]}[/bold {Colors.AI_ACCENT}]")

                badge_str = f"  {' '.join(badges)}" if badges else ""
                tbl_node.add(f"[dim {Colors.TEXT_TERTIARY}]{name}[/dim {Colors.TEXT_TERTIARY}] [dim]({ctype})[/dim]{badge_str}")

        console.print(root)
        console.print()

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        console.print(f"\n[{Colors.TEXT_MUTED}]Operation cancelled.[/{Colors.TEXT_MUTED}]")
        raise typer.Exit(0)
    except Exception as e:
        handle_error(e, "Schema Explorer", suggest_action="Run 'teshq db introspect' to refresh your schema.")
        raise typer.Exit(1)


@app.command(name="preview", help="Preview sample rows from any table.")
def preview_table(
    table_name: str = typer.Argument(..., help="Name of the table to preview."),
    limit: int = typer.Option(
        5,
        "--limit",
        "-n",
        help="Number of rows to preview.",
        rich_help_panel=PANEL_PREVIEW,
    ),
) -> None:
    """Preview sample rows from a specific database table."""
    from teshq.cli.ui import print_results_table
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
    except typer.Exit:
        raise
    except KeyboardInterrupt:
        console.print(f"\n[{Colors.TEXT_MUTED}]Operation cancelled.[/{Colors.TEXT_MUTED}]")
        raise typer.Exit(0)
    except Exception as e:
        handle_error(
            e,
            f"Table Preview ({table_name})",
            suggest_action=f"Verify table '{table_name}' exists using 'teshq db explore'",
        )
        raise typer.Exit(1)


# Register alias for explore
app.command(name="tree", help="Alias for 'teshq db explore'")(explore_schema)


if __name__ == "__main__":
    app()

