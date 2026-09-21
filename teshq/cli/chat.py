"""
Interactive Chat / REPL Mode for TESH-Query (`teshq chat` / `teshq repl`).

Provides a high-velocity, conversational database exploration session with
multi-turn context, slash commands, instant schema discovery, and effortless exports.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from teshq.config.loader import get_database_url as get_db_url, get_settings
from teshq.core.engine import TeshEngine
from teshq.core.exceptions import TeshqConfigurationError
from teshq.utils.output import QueryResult
from teshq.utils.save import save_to_csv, save_to_excel
from teshq.cli.ui.banner import print_hero_banner, print_hud, print_suggested_prompts
from teshq.cli.ui.cards import print_error_card, print_metrics, print_sql_card
from teshq.cli.ui.tables import print_results_table
from teshq.cli.ui.theme import Colors, Icons, ROUNDED_BOX, console, err_console

app = typer.Typer(help="Interactive multi-turn SQL chat session.")


def _get_env_summary() -> tuple[str, str, str, Optional[int]]:
    """Gather quick environment status for the HUD without raising."""
    db_type = "Database"
    db_status = "Not Connected"
    llm_name = "Gemini 1.5"
    table_count = None

    try:
        settings = get_settings()
        if settings.llm_provider.lower() == "azure":
            llm_name = "Azure OpenAI"
        elif settings.llm_provider.lower() == "local":
            llm_name = "Local GGUF"
        else:
            llm_name = "Gemini 1.5 Pro"

        db_url = get_db_url()
        if db_url:
            if "postgres" in db_url:
                db_type = "PostgreSQL"
            elif "sqlite" in db_url:
                db_type = "SQLite"
            elif "mysql" in db_url:
                db_type = "MySQL"
            elif "oracle" in db_url:
                db_type = "Oracle"
            else:
                db_type = "SQL DB"
            db_status = "Connected"
    except Exception:
        pass

    # Check schema cache
    try:
        from teshq.config.paths import get_schema_path
        schema_path = get_schema_path("schema.txt")
        if schema_path.exists():
            content = schema_path.read_text(encoding="utf-8", errors="ignore")
            # Count tables in schema.txt
            tables = [line for line in content.splitlines() if line.startswith("TABLE ") or line.startswith("Table ")]
            if tables:
                table_count = len(tables)
    except Exception:
        pass

    return db_status, db_type, llm_name, table_count


def _render_help_sheet() -> Panel:
    """Build the visual shortcut and slash-command guide."""
    table = Table(box=ROUNDED_BOX, border_style=Colors.BORDER_SUBTLE, show_header=True)
    table.add_column("Command", style=f"bold {Colors.PRIMARY}", width=22)
    table.add_column("Action", style=Colors.TEXT_MUTED)

    commands = [
        ("/tables", "Explore all tables and row counts in a visual tree"),
        ("/schema [table]", "Inspect column types and foreign keys for a table"),
        ("/sql", "Display the generated SQL query of the last execution"),
        ("/export <csv|excel> [file]", "Quick-export the active result set to disk"),
        ("/clear", "Clear terminal screen and redraw status HUD"),
        ("/model [name]", "Show or switch the inference model provider"),
        ("/help", "Show this interactive command guide"),
        ("exit, quit, :q", "Leave the interactive session safely"),
    ]

    for cmd, desc in commands:
        table.add_row(cmd, desc)

    return Panel(
        table,
        title=f"[bold {Colors.TEXT}]{Icons.sparkle()} Interactive Shortcuts & Slash Commands[/bold {Colors.TEXT}]",
        title_align="left",
        border_style=Colors.BORDER,
        box=ROUNDED_BOX,
        padding=(0, 1),
    )


def _render_schema_tree(engine: TeshEngine) -> Tree:
    """Build a visual Rich Tree of the database schema."""
    db_name = "Database Schema"
    db_url = getattr(engine, '_db_url', '') or ''
    dialect = getattr(engine, '_dialect', 'SQL') or 'SQL'
    if db_url:
        db_name = db_url.split("@")[-1].split("/")[-1] if "/" in db_url else "Database"

    root = Tree(f"[bold {Colors.PRIMARY}]{Icons.database()} {db_name}[/bold {Colors.PRIMARY}] [dim]({dialect.upper()})[/dim]")

    try:
        from teshq.core.schema_graph import SchemaGraph
        graph = SchemaGraph.from_schema_file()
        all_tables = graph.get_all_tables()

        if not all_tables:
            root.add("[italic dim]No cached schema found. Run 'teshq db introspect' first.[/italic dim]")
            return root

        for tbl in sorted(all_tables):
            cols = graph.get_columns_for_table(tbl)
            fks = graph.get_foreign_keys_for_table(tbl)
            fk_col_map = {fk.get("constrained_column"): fk.get("referred_table") for fk in fks}

            tbl_node = root.add(f"[bold {Colors.TEXT}]{Icons.table()} {tbl}[/bold {Colors.TEXT}] [dim]({len(cols)} columns)[/dim]")

            for col in cols:
                name = col.get("name", "")
                ctype = col.get("type", "")
                is_pk = col.get("primary_key", False)

                badges = []
                if is_pk:
                    badges.append(f"[bold {Colors.WARNING}]{Icons.key()} PK[/bold {Colors.WARNING}]")
                if name in fk_col_map:
                    badges.append(f"[bold {Colors.SECONDARY}]{Icons.link()} FK ➔ {fk_col_map[name]}[/bold {Colors.SECONDARY}]")

                badge_str = f"  {' '.join(badges)}" if badges else ""
                tbl_node.add(f"[dim {Colors.MUTED}]{name}[/dim {Colors.MUTED}] [dim]({ctype})[/dim]{badge_str}")

    except Exception as e:
        root.add(f"[dim red]Could not parse schema graph: {e}[/dim red]")

    return root


@app.callback(invoke_without_command=True)
def interactive_chat(
    ctx: typer.Context,
    local: bool = typer.Option(False, "--local", help="Force local GGUF model."),
    cloud: bool = typer.Option(False, "--cloud", help="Force cloud model."),
) -> None:
    """Launch the interactive TESH-Query conversational terminal."""
    # Header & Welcome
    console.clear()
    print_hero_banner()

    db_status, db_type, llm_name, table_count = _get_env_summary()
    print_hud(db_status=db_status, db_type=db_type, llm_model=llm_name, schema_tables_count=table_count)
    console.print()
    print_suggested_prompts()

    provider_override = None
    if local:
        provider_override = "local"
    elif cloud:
        provider_override = "google"

    # Initialize Engine once for session speed
    engine: Optional[TeshEngine] = None
    try:
        engine = TeshEngine(provider=provider_override)
    except Exception as e:
        console.print(f"[bold {Colors.WARNING}]{Icons.warn()} Note:[/bold {Colors.WARNING}] Engine will initialize on first query ({e}).")

    last_sql: Optional[str] = None
    last_parameters: Optional[Dict[str, Any]] = None
    last_result: Optional[QueryResult] = None
    last_nl_query: Optional[str] = None
    last_dialect: str = "SQL"

    # Interactive Prompt Loop
    while True:
        try:
            prompt_str = f"[bold {Colors.PRIMARY}]tesh[/bold {Colors.PRIMARY}] [dim {Colors.MUTED}]❯[/dim {Colors.MUTED}] "
            user_input = console.input(prompt_str).strip()
        except (KeyboardInterrupt, EOFError):
            console.print(f"\n[dim]Leaving session. Goodbye! {Icons.sparkle()}[/dim]\n")
            break

        if not user_input:
            continue

        # Check exit commands
        if user_input.lower() in ("exit", "quit", ":q", "q"):
            console.print(f"\n[bold {Colors.SUCCESS}]{Icons.check()}[/bold {Colors.SUCCESS}] [dim]Session ended. Happy querying![/dim]\n")
            break

        # -------------------------------------------------------------------
        # Slash Commands
        # -------------------------------------------------------------------
        if user_input.startswith("/"):
            parts = user_input.split(maxsplit=2)
            cmd = parts[0].lower()

            if cmd in ("/help", "/?"):
                console.print(_render_help_sheet())
                console.print()
                continue

            elif cmd in ("/clear", "/cls"):
                console.clear()
                print_hud(db_status=db_status, db_type=db_type, llm_model=llm_name, schema_tables_count=table_count)
                console.print()
                continue

            elif cmd in ("/tables", "/schema"):
                if not engine:
                    try:
                        engine = TeshEngine(provider=provider_override)
                    except Exception as e:
                        print_error_card(e, context="Schema Inspection")
                        continue
                tree = _render_schema_tree(engine)
                console.print(tree)
                console.print()
                continue

            elif cmd == "/sql":
                if not last_sql:
                    console.print(f"[{Colors.MUTED}]No query has been generated yet in this session.[/{Colors.MUTED}]\n")
                else:
                    print_sql_card(last_sql, dialect=last_dialect, parameters=last_parameters, title="Last Generated SQL")
                    console.print()
                continue

            elif cmd == "/export":
                if not last_result or not last_result.dataframe is not None:
                    console.print(f"[bold {Colors.WARNING}]{Icons.warn()}[/bold {Colors.WARNING}] No active query results to export.\n")
                    continue

                fmt = parts[1].lower() if len(parts) > 1 else "csv"
                default_name = f"query_results_{int(time.time())}"
                target_path = parts[2] if len(parts) > 2 else f"{default_name}.{fmt}"

                try:
                    df = last_result.dataframe
                    if fmt in ("excel", "xlsx"):
                        if not target_path.endswith((".xlsx", ".xls")):
                            target_path += ".xlsx"
                        save_to_excel(df, target_path)
                    else:
                        if not target_path.endswith(".csv"):
                            target_path += ".csv"
                        save_to_csv(df, target_path)

                    console.print(f"[bold {Colors.SUCCESS}]{Icons.check()}[/bold {Colors.SUCCESS}] Exported {len(df):,} rows to [bold {Colors.TEXT}]{target_path}[/bold {Colors.TEXT}]\n")
                except Exception as e:
                    print_error_card(e, context="Export Results")
                continue

            elif cmd == "/model":
                if len(parts) > 1:
                    new_provider = parts[1].lower()
                    try:
                        engine = TeshEngine(provider=new_provider)
                        console.print(f"[bold {Colors.SUCCESS}]{Icons.check()}[/bold {Colors.SUCCESS}] Switched model provider to: [bold {Colors.PRIMARY}]{new_provider}[/bold {Colors.PRIMARY}]\n")
                    except Exception as e:
                        print_error_card(e, context="Switch Provider")
                else:
                    console.print(f"[{Colors.MUTED}]Active model provider: [bold {Colors.PRIMARY}]{llm_name}[/bold {Colors.PRIMARY}][/{Colors.MUTED}]\n")
                continue

            else:
                console.print(f"[bold {Colors.WARNING}]{Icons.warn()} Unknown command:[/bold {Colors.WARNING}] '{cmd}'. Type [bold {Colors.PRIMARY}]/help[/bold {Colors.PRIMARY}] for available commands.\n")
                continue

        # -------------------------------------------------------------------
        # Natural Language Query Execution
        # -------------------------------------------------------------------
        try:
            if not engine:
                engine = TeshEngine(provider=provider_override)

            last_dialect = getattr(engine, "_dialect", "SQL") or "SQL"

            # Conversational multi-turn enrichment
            request_text = user_input
            follow_up_triggers = ("now ", "only ", "filter ", "sort ", "order by ", "group by ", "limit ", "also ", "and ")
            if last_nl_query and any(user_input.lower().startswith(t) for t in follow_up_triggers):
                request_text = f"Context from previous query '{last_nl_query}' with SQL: {last_sql}. Follow-up request: {user_input}"

            with console.status(f"[{Colors.PRIMARY}]{Icons.bolt()} Synthesizing SQL & querying database...[/{Colors.PRIMARY}]", spinner="dots"):
                engine_result = engine.query(request_text, dry_run=False)

            last_sql = engine_result.sql
            last_parameters = engine_result.parameters
            last_nl_query = user_input

            # Render SQL card
            print_sql_card(last_sql, dialect=last_dialect, parameters=last_parameters, title="Generated SQL")

            # Wrap and display results
            result = QueryResult(
                results=engine_result.rows,
                query=last_sql,
                parameters=last_parameters,
                natural_language_query=user_input,
            )
            last_result = result

            result.print_query_table()

            # Execution telemetry metrics
            print_metrics(
                plan_latency_ms=engine_result.plan_latency_ms,
                sql_latency_ms=engine_result.sql_latency_ms,
                exec_latency_ms=engine_result.exec_latency_ms,
                total_tokens=engine_result.total_tokens,
                cost_estimate_usd=engine_result.cost_estimate_usd,
                row_count=len(result),
            )
            console.print()

        except Exception as e:
            print_error_card(e, context="Query Processing")
            console.print()
