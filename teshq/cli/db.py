import os
import time

import typer
from dotenv import load_dotenv
from sqlalchemy.engine import make_url

from teshq.cli.logging import CLILogger
from teshq.cli.ui import (
    error,
    handle_error,
    info,
    print_header,
    print_results_table,
    status,
    success,
    tip,
    warning,
)
from teshq.cli.ui.theme import ROUNDED_BOX, Colors, Icons, console
from teshq.config.loader import get_database_url as get_configured_database_url
from teshq.core.connection import connection_manager
from teshq.core.introspect import introspect_db

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
                if url_obj.username:
                    masked = f"{backend}://{user_str}*****@{host}{port_str}/{db_name}"
                else:
                    masked = f"{backend}://{host}{port_str}/{db_name}"
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

    named_conns = connection_manager.list_connections()
    if named_conns:
        named_info = f"[bold {Colors.SUCCESS}]{len(named_conns)} connection(s)[/bold {Colors.SUCCESS}] configured"
    else:
        named_info = f"[{Colors.TEXT_MUTED}]0 configured (use 'teshq db connection add')[/{Colors.TEXT_MUTED}]"

    p = Colors.PRIMARY
    sec = Colors.TEXT_SECONDARY
    tert = Colors.TEXT_TERTIARY
    cmd_conn = f"  [{p}]teshq db connection list[/{p}]   [{sec}]List configured named connections[/{sec}]"
    cmd_exp = f"  [{p}]teshq db explore[/{p}]           [{sec}]Display visual interactive schema tree[/{sec}]"
    cmd_int = f"  [{p}]teshq db introspect[/{p}]        [{sec}]Re-run schema introspection & relationships[/{sec}]"
    cmd_prv = f"  [{p}]teshq db preview <table-name>[/{p}]  [{sec}]Preview sample records from any table[/{sec}]"
    cmd_cfg = f"  [{p}]teshq config --db[/{p}]          [{sec}]Configure or switch database URL[/{sec}]"

    hud_text = (
        f"[{tert}]Connection Status:[/{tert}] {db_status}\n"
        f"[{tert}]Database URL:[/{tert}]      {db_detail}\n"
        f"[{tert}]Named Connections:[/{tert}] {named_info}\n"
        f"[{tert}]Introspected Schema:[/{tert}] {schema_info}\n\n"
        f"[{tert}]Available Commands:[/{tert}]\n"
        f"{cmd_conn}\n{cmd_exp}\n{cmd_int}\n{cmd_prv}\n{cmd_cfg}"
    )

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
    connection: str = typer.Option(
        None,
        "--connection",
        "-c",
        help="Named database connection to introspect.",
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
        if connection and not db_url:
            named = connection_manager.get_named_connection(connection)
            db_url = named.db_url

        print_header("Database Schema Introspection", level=2)

        if logging_active:
            cli_logger.log_command_start({
                "db_url": "***" if db_url else None,
                "connection": connection,
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
def explore_schema(
    connection: str = typer.Option(
        None,
        "--connection",
        "-c",
        help="Target named database connection to explore.",
    ),
) -> None:
    """Explore introspected schema in an interactive visual tree."""
    from rich.tree import Tree
    from teshq.core.schema_graph import SchemaGraph
    from teshq.config.paths import get_db_schema_path

    print_header("Database Schema Explorer", level=2)

    try:
        if connection:
            conn_obj = connection_manager.get_named_connection(connection)
            schema_path = get_db_schema_path(conn_obj.db_url).parent / "schema.json"
            if not schema_path.exists():
                from teshq.core.introspect import introspect_db
                introspect_db(db_url=conn_obj.db_url)
            graph = SchemaGraph.from_schema_file(str(schema_path))
        else:
            graph = SchemaGraph.from_schema_file()
        tables = graph.get_all_tables()

        if not tables:
            tip("No cached schema found. Run 'teshq db introspect' first to introspect your database.")
            raise typer.Exit(0)

        root = Tree(
            f"[bold {Colors.PRIMARY}]{Icons.database()} Introspected Database Schema[/bold {Colors.PRIMARY}] "
            f"[dim]({len(tables)} tables)[/dim]"
        )

        for tbl in sorted(tables):
            cols = graph.get_columns_for_table(tbl)
            fks = graph.get_foreign_keys_for_table(tbl)
            fk_map = {fk.get("constrained_column"): fk.get("referred_table") for fk in fks}

            tbl_node = root.add(
                f"[bold {Colors.TEXT_PRIMARY}]{Icons.table()} {tbl}[/bold {Colors.TEXT_PRIMARY}] "
                f"[dim]({len(cols)} columns)[/dim]"
            )

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
                col_label = (
                    f"[dim {Colors.TEXT_TERTIARY}]{name}[/dim {Colors.TEXT_TERTIARY}] "
                    f"[dim]({ctype})[/dim]{badge_str}"
                )
                tbl_node.add(col_label)

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
    connection: str = typer.Option(
        None,
        "--connection",
        "-c",
        help="Target named database connection.",
        rich_help_panel=PANEL_DB,
    ),
) -> None:
    """Preview sample rows from a specific database table."""
    from teshq.core.engine import TeshEngine

    try:
        from teshq.config.loader import get_database_url as get_db_url
        engine = TeshEngine(connection_name=connection)
        query = f"SELECT * FROM {table_name} LIMIT {limit};"

        with status(f"Fetching sample data from {table_name}..."):
            target_url = None
            if connection:
                try:
                    conn_obj = connection_manager.get_named_connection(connection)
                    target_url = conn_obj.db_url
                except Exception:
                    pass
            if not target_url:
                target_url = engine.db_url or get_db_url()

            rows = connection_manager.execute_query_with_timeout(target_url, query)

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


conn_app = typer.Typer(
    name="connection",
    help="Manage named multi-database connections.",
    invoke_without_command=False,
)


@conn_app.command(name="add", help="Add or update a named database connection.")
def add_connection_cmd(
    name: str = typer.Argument(..., help="Unique identifier for this connection."),
    db_url: str = typer.Argument(..., help="Database connection URL."),
    default: bool = typer.Option(False, "--default", "-d", help="Set this connection as the default."),
    description: str = typer.Option(None, "--description", "--desc", help="Optional description."),
):
    try:
        connection_manager.add_connection(
            name=name,
            db_url=db_url,
            set_as_default=default,
            description=description,
            overwrite=True,
            persist=True,
        )
        success(f"Connection '{name}' registered successfully.")
        if default:
            info(f"Connection '{name}' set as active default.")
    except Exception as e:
        handle_error(e, "Add Connection")
        raise typer.Exit(1)


@conn_app.command(name="list", help="List all configured named connections.")
def list_connections_cmd():
    from rich.table import Table

    conns = connection_manager.list_connections()
    if not conns:
        tip("No named connections configured yet. Run 'teshq db connection add <name> <db_url>' to add one.")
        return

    table = Table(
        title="Configured Database Connections",
        box=ROUNDED_BOX,
        border_style=Colors.BORDER_DEFAULT,
    )
    table.add_column("Name", style=f"bold {Colors.PRIMARY}")
    table.add_column("Dialect", style=Colors.TEXT_SECONDARY)
    table.add_column("URL", style=Colors.TEXT_TERTIARY)
    table.add_column("Default", justify="center")
    table.add_column("Description", style=Colors.TEXT_MUTED)

    for c in conns:
        is_def = f"[bold {Colors.SUCCESS}]● Yes[/bold {Colors.SUCCESS}]" if c.get("is_default") else "[dim]No[/dim]"
        desc = c.get("description") or "—"
        masked = c.get("masked_url") or c.get("url") or c.get("db_url", "—")
        dialect_name = c.get("dialect", "unknown")
        if hasattr(dialect_name, "value"):
            dialect_name = dialect_name.value
        table.add_row(c["name"], str(dialect_name), masked, is_def, desc)

    console.print(table)


@conn_app.command(name="remove", help="Remove a named database connection.")
def remove_connection_cmd(
    name: str = typer.Argument(..., help="Name of connection to remove.")
):
    try:
        connection_manager.remove_connection(name, persist=True)
        success(f"Connection '{name}' removed successfully.")
    except KeyError:
        warning(f"Connection '{name}' was not found.")


@conn_app.command(name="test", help="Test connectivity to a named database connection.")
def test_connection_cmd(
    name: str = typer.Argument(..., help="Name of connection to test.")
):
    with status(f"Testing connectivity to '{name}'..."):
        ok, msg = connection_manager.test_named_connection(name)
    if ok:
        success(f"Connection '{name}' succeeded. ({msg})")
    else:
        error(f"Connection '{name}' failed: {msg}")
        raise typer.Exit(1)


@conn_app.command(name="default", help="Set the default named database connection.")
def default_connection_cmd(
    name: str = typer.Argument(..., help="Name of connection to set as default.")
):
    try:
        connection_manager.set_default_connection(name, persist=True)
        success(f"Default connection updated to '{name}'.")
    except Exception as e:
        handle_error(e, "Set Default Connection")
        raise typer.Exit(1)


app.add_typer(conn_app, name="connection", help="Manage named multi-database connections.")
app.add_typer(conn_app, name="connections", help="Manage named multi-database connections (alias).")


if __name__ == "__main__":
    app()
