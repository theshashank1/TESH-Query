"""
Interactive Chat / REPL Mode for TESH-Query (`teshq chat` / `teshq repl`).

Redesigned as a precision instrument: command blocks, ambient status bar,
6-stage cognitive progress, inline help, and contextual AI hints.
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
from teshq.utils.save import save_to_csv, save_to_excel, resolve_output_path
from teshq.cli.ui.banner import print_hero_banner, print_hud, print_suggested_prompts
from teshq.cli.ui.cards import print_error_card, print_metrics, print_sql_card
from teshq.cli.ui.tables import print_results_table, render_results_table
from teshq.cli.ui.blocks import (
    CommandBlock,
    StageTracker,
    QUERY_STAGES,
    render_stage_line,
)
from teshq.cli.ui.status_bar import print_status_bar
from teshq.cli.ui.palette import print_help_sheet, render_help_sheet
from teshq.cli.ui.theme import Colors, Icons, Spacing, ROUNDED_BOX, console, err_console

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
            tables = [line for line in content.splitlines() if line.startswith("TABLE ") or line.startswith("Table ")]
            if tables:
                table_count = len(tables)
    except Exception:
        pass

    return db_status, db_type, llm_name, table_count


def _extract_db_name(db_url: Optional[str]) -> str:
    """Extract a human-readable database name from the connection URL."""
    if not db_url:
        return ""
    try:
        if "sqlite" in db_url.lower():
            # Extract filename from sqlite path
            parts = db_url.split("/")
            name = parts[-1] if parts else ""
            # Remove extension
            if "." in name:
                name = name.rsplit(".", 1)[0]
            return name
        elif "@" in db_url and "/" in db_url:
            return db_url.split("/")[-1]
    except Exception:
        pass
    return ""


def _render_schema_tree(engine: TeshEngine) -> Tree:
    """Build a visual Rich Tree of the database schema."""
    db_name = "Database Schema"
    db_url = getattr(engine, '_db_url', '') or ''
    dialect = getattr(engine, '_dialect', 'SQL') or 'SQL'
    if db_url:
        db_name = db_url.split("@")[-1].split("/")[-1] if "/" in db_url else "Database"

    root = Tree(
        f"[bold {Colors.PRIMARY}]{Icons.database()} {db_name}"
        f"[/bold {Colors.PRIMARY}] [{Colors.TEXT_MUTED}]({dialect.upper()})[/{Colors.TEXT_MUTED}]"
    )

    try:
        from teshq.core.schema_graph import SchemaGraph
        graph = SchemaGraph.from_schema_file()
        all_tables = graph.get_all_tables()

        if not all_tables:
            root.add(
                f"[italic {Colors.TEXT_MUTED}]No cached schema. "
                f"Run 'teshq db introspect' first.[/italic {Colors.TEXT_MUTED}]"
            )
            return root

        for tbl in sorted(all_tables):
            cols = graph.get_columns_for_table(tbl)
            fks = graph.get_foreign_keys_for_table(tbl)
            fk_col_map = {fk.get("constrained_column"): fk.get("referred_table") for fk in fks}

            tbl_node = root.add(
                f"[bold {Colors.TEXT_PRIMARY}]{Icons.table()} {tbl}"
                f"[/bold {Colors.TEXT_PRIMARY}] "
                f"[{Colors.TEXT_MUTED}]({len(cols)} cols)[/{Colors.TEXT_MUTED}]"
            )

            for col in cols:
                name = col.get("name", "")
                ctype = col.get("type", "")
                is_pk = col.get("primary_key", False)

                badges = []
                if is_pk:
                    badges.append(
                        f"[bold {Colors.WARNING}]{Icons.key()} PK[/bold {Colors.WARNING}]"
                    )
                if name in fk_col_map:
                    badges.append(
                        f"[{Colors.AI_ACCENT}]{Icons.link()} FK {Icons.arrow()} "
                        f"{fk_col_map[name]}[/{Colors.AI_ACCENT}]"
                    )

                badge_str = f"  {' '.join(badges)}" if badges else ""
                tbl_node.add(
                    f"[{Colors.TEXT_TERTIARY}]{name}[/{Colors.TEXT_TERTIARY}] "
                    f"[{Colors.TEXT_MUTED}]({ctype})[/{Colors.TEXT_MUTED}]{badge_str}"
                )

    except Exception as e:
        root.add(f"[{Colors.ERROR}]Could not parse schema: {e}[/{Colors.ERROR}]")

    return root


def _render_session_summary(
    query_count: int,
    total_time_s: float,
    total_tokens: int,
) -> Text:
    """Render a compact session summary on exit."""
    summary = Text()
    summary.append(f"\n  {Icons.check()} ", style=f"bold {Colors.SUCCESS}")
    parts = []
    parts.append(f"{query_count} quer{'ies' if query_count != 1 else 'y'}")
    if total_time_s > 0:
        parts.append(f"{total_time_s:.1f}s total")
    if total_tokens > 0:
        parts.append(f"{total_tokens:,} tokens")
    summary.append(
        f" {Icons.separator()} ".join(parts),
        style=f"{Colors.TEXT_TERTIARY}",
    )
    summary.append("\n")
    return summary


def copy_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard across Windows, macOS, and Linux without extra dependencies."""
    if not text:
        return False
    # Windows clip.exe
    if sys.platform == "win32":
        try:
            import subprocess
            p = subprocess.Popen(
                ["clip"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=True,
            )
            p.communicate(text.encode("utf-8"))
            if p.returncode == 0:
                return True
        except Exception:
            pass
    # macOS pbcopy
    elif sys.platform == "darwin":
        try:
            import subprocess
            p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            p.communicate(text.encode("utf-8"))
            if p.returncode == 0:
                return True
        except Exception:
            pass
    # Linux xclip / wl-copy / xsel
    else:
        for cmd in [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]:
            try:
                import subprocess
                p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                p.communicate(text.encode("utf-8"))
                if p.returncode == 0:
                    return True
            except Exception:
                continue
    return False


def clear_terminal_screen() -> None:
    """Clear terminal screen and scrollback buffer across platforms."""
    try:
        if os.name == "nt":
            os.system("cls")
        else:
            os.system("clear")
    except Exception:
        pass
    console.clear()


def clear_command_history() -> None:
    """Clear interactive input history so Up-arrow begins fresh."""
    try:
        import importlib
        pyrepl_rl = importlib.import_module("_pyrepl.readline")
        if hasattr(pyrepl_rl, "clear_history"):
            pyrepl_rl.clear_history()
    except Exception:
        pass

    try:
        import readline
        if hasattr(readline, "clear_history"):
            readline.clear_history()
    except Exception:
        pass

    if sys.platform == "win32":
        try:
            os.system("doskey /listsize=0 >nul 2>&1")
            os.system("doskey /listsize=50 >nul 2>&1")
        except Exception:
            pass


@app.callback(invoke_without_command=True)
def interactive_chat(
    ctx: typer.Context,
    local: bool = typer.Option(False, "--local", help="Force local GGUF model."),
    cloud: bool = typer.Option(False, "--cloud", help="Force cloud model."),
) -> None:
    """Launch the interactive TESH-Query conversational terminal."""
    # ── Clear Past Screen & Command History ────────────────────────────
    clear_command_history()
    clear_terminal_screen()
    print_hero_banner()

    db_status, db_type, llm_name, table_count = _get_env_summary()
    print_hud(db_status=db_status, db_type=db_type, llm_model=llm_name, schema_tables_count=table_count)

    # Extract db name for status bar
    db_name = ""
    try:
        db_url = get_db_url()
        db_name = _extract_db_name(db_url)
    except Exception:
        pass

    console.print()
    print_suggested_prompts()
    console.print()

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
        console.print(
            f"  [{Colors.WARNING}]{Icons.warn()} Engine will initialize on first query"
            f"[/{Colors.WARNING}] [{Colors.TEXT_MUTED}]({e})[/{Colors.TEXT_MUTED}]"
        )

    last_sql: Optional[str] = None
    last_parameters: Optional[Dict[str, Any]] = None
    last_result: Optional[QueryResult] = None
    last_nl_query: Optional[str] = None
    last_dialect: str = "SQL"
    last_error: Optional[str] = None

    # Session stats
    session_queries = 0
    session_total_time = 0.0
    session_total_tokens = 0
    session_history: List[str] = []

    # Reset block counter for this session
    CommandBlock.reset_counter()

    # ── Interactive Prompt Loop ───────────────────────────────────────
    while True:
        try:
            # Minimal prompt: just the › character
            prompt_str = f"[bold {Colors.PRIMARY}]{Icons.prompt()}[/bold {Colors.PRIMARY}] "
            user_input = console.input(prompt_str).strip()
        except (KeyboardInterrupt, EOFError):
            console.print(_render_session_summary(
                session_queries, session_total_time, session_total_tokens,
            ))
            break

        if not user_input:
            continue

        session_history.append(user_input)

        # Clean input and strip brackets if user clicked, typed, or copied bracketed hint [Action]
        clean_input = user_input.strip()
        if clean_input.startswith("[") and clean_input.endswith("]"):
            clean_input = clean_input[1:-1].strip()

        # Check exit commands
        if clean_input.lower() in ("exit", "quit", ":q", "q"):
            console.print(_render_session_summary(
                session_queries, session_total_time, session_total_tokens,
            ))
            break

        # Map plain-text action chips or shortcuts to canonical slash commands
        is_slash = clean_input.startswith("/")
        cmd_candidate = clean_input.lower()

        if not is_slash:
            if cmd_candidate in ("copy sql", "copy"):
                clean_input = "/copy sql"
            elif cmd_candidate in ("copy results", "copy data"):
                clean_input = "/copy results"
            elif cmd_candidate in ("copy error",):
                clean_input = "/copy error"
            elif cmd_candidate in ("rerun", "retry"):
                clean_input = "/rerun"
            elif cmd_candidate == "explain":
                clean_input = "/explain"
            elif cmd_candidate.startswith("export "):
                clean_input = f"/{clean_input}"
            elif cmd_candidate == "export":
                clean_input = "/export"
            elif cmd_candidate in ("tables", "schema"):
                clean_input = f"/{clean_input}"
            elif cmd_candidate in ("clear", "cls"):
                clean_input = "/clear"
            elif cmd_candidate in ("help", "?"):
                clean_input = "/help"
            elif cmd_candidate in ("history", "hist"):
                clean_input = "/history"

        # ── Slash Commands ────────────────────────────────────────────
        if clean_input.startswith("/"):
            parts = clean_input.split(maxsplit=2)
            cmd = parts[0].lower()

            if cmd in ("/help", "/?"):
                print_help_sheet()
                continue

            elif cmd in ("/clear", "/cls"):
                clear_command_history()
                clear_terminal_screen()
                print_status_bar(
                    db_status=db_status, db_type=db_type, db_name=db_name,
                    llm_model=llm_name, schema_tables_count=table_count,
                    session_queries=session_queries,
                )
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
                    console.print(
                        f"  [{Colors.TEXT_TERTIARY}]No query generated yet in this session."
                        f"[/{Colors.TEXT_TERTIARY}]\n"
                    )
                else:
                    print_sql_card(
                        last_sql, dialect=last_dialect,
                        parameters=last_parameters, title="Last SQL",
                    )
                    console.print()
                continue

            elif cmd == "/export":
                if not last_result or not last_result.dataframe is not None:
                    console.print(
                        f"  [{Colors.WARNING}]{Icons.warn()} No active results to export."
                        f"[/{Colors.WARNING}]\n"
                    )
                    continue

                fmt = parts[1].lower() if len(parts) > 1 else "csv"
                custom_name = parts[2] if len(parts) > 2 else None

                # Map format aliases to extensions
                ext_map = {"excel": "xlsx", "xlsx": "xlsx", "xls": "xlsx",
                           "csv": "csv", "sqlite": "db", "db": "db"}
                ext = ext_map.get(fmt, "csv")

                try:
                    df = last_result.dataframe
                    resolved_path, display_path = resolve_output_path(
                        query_text=last_nl_query,
                        ext=ext,
                        custom_path=custom_name,
                    )
                    target_path = str(resolved_path)

                    if fmt in ("excel", "xlsx", "xls"):
                        if not target_path.endswith((".xlsx", ".xls")):
                            target_path += ".xlsx"
                            display_path += ".xlsx"
                        save_to_excel(df, target_path)
                    elif fmt in ("sqlite", "db"):
                        from teshq.utils.save import save_to_sqlite
                        if not target_path.endswith((".db", ".sqlite", ".sqlite3")):
                            target_path += ".db"
                            display_path += ".db"
                        save_to_sqlite(df, target_path, table_name="results")
                    else:
                        if not target_path.endswith(".csv"):
                            target_path += ".csv"
                            display_path += ".csv"
                        save_to_csv(df, target_path)

                    console.print(
                        f"  [{Colors.SUCCESS}]{Icons.check()}[/{Colors.SUCCESS}] "
                        f"Exported {len(df):,} rows to "
                        f"[bold {Colors.TEXT_PRIMARY}]{display_path}"
                        f"[/bold {Colors.TEXT_PRIMARY}]\n"
                    )
                except Exception as e:
                    print_error_card(e, context="Export Results")
                continue

            elif cmd == "/model":
                if len(parts) > 1:
                    new_provider = parts[1].lower()
                    try:
                        engine = TeshEngine(provider=new_provider)
                        llm_name = new_provider.title()
                        console.print(
                            f"  [{Colors.SUCCESS}]{Icons.check()}[/{Colors.SUCCESS}] "
                            f"Switched to [{Colors.PRIMARY}]{new_provider}"
                            f"[/{Colors.PRIMARY}]\n"
                        )
                    except Exception as e:
                        print_error_card(e, context="Switch Provider")
                else:
                    console.print(
                        f"  [{Colors.TEXT_TERTIARY}]Active provider: "
                        f"[bold {Colors.PRIMARY}]{llm_name}"
                        f"[/bold {Colors.PRIMARY}][/{Colors.TEXT_TERTIARY}]\n"
                    )
                continue

            elif cmd == "/copy":
                target = parts[1].lower() if len(parts) > 1 else "sql"
                if target in ("sql", "query"):
                    if not last_sql:
                        console.print(
                            f"  [{Colors.TEXT_TERTIARY}]No SQL query generated yet to copy."
                            f"[/{Colors.TEXT_TERTIARY}]\n"
                        )
                    else:
                        if copy_to_clipboard(last_sql):
                            console.print(
                                f"  [{Colors.SUCCESS}]{Icons.check()}[/{Colors.SUCCESS}] "
                                f"[bold {Colors.TEXT_PRIMARY}]SQL copied to system clipboard![/bold {Colors.TEXT_PRIMARY}]\n"
                            )
                        else:
                            console.print(
                                f"  [{Colors.WARNING}]{Icons.warn()} Clipboard not available in this environment. "
                                f"Here is the SQL query:[/{Colors.WARNING}]\n"
                            )
                            print_sql_card(last_sql, dialect=last_dialect, parameters=last_parameters, title="SQL")
                            console.print()
                elif target in ("results", "data", "result", "csv"):
                    if not last_result or last_result.dataframe is None:
                        console.print(
                            f"  [{Colors.WARNING}]{Icons.warn()} No active results to copy."
                            f"[/{Colors.WARNING}]\n"
                        )
                    else:
                        df = last_result.dataframe
                        csv_data = df.to_csv(index=False)
                        if copy_to_clipboard(csv_data):
                            console.print(
                                f"  [{Colors.SUCCESS}]{Icons.check()}[/{Colors.SUCCESS}] "
                                f"[bold {Colors.TEXT_PRIMARY}]Results ({len(df):,} rows) copied to clipboard as CSV![/bold {Colors.TEXT_PRIMARY}]\n"
                            )
                        else:
                            console.print(
                                f"  [{Colors.WARNING}]{Icons.warn()} Clipboard not available in this environment.[/{Colors.WARNING}]\n"
                            )
                elif target in ("error", "err"):
                    if not last_error:
                        console.print(
                            f"  [{Colors.TEXT_TERTIARY}]No error recorded to copy.[/{Colors.TEXT_TERTIARY}]\n"
                        )
                    else:
                        if copy_to_clipboard(last_error):
                            console.print(
                                f"  [{Colors.SUCCESS}]{Icons.check()}[/{Colors.SUCCESS}] "
                                f"[bold {Colors.TEXT_PRIMARY}]Error details copied to clipboard![/bold {Colors.TEXT_PRIMARY}]\n"
                            )
                        else:
                            console.print(
                                f"  [{Colors.WARNING}]{Icons.warn()} Clipboard not available.[/{Colors.WARNING}]\n"
                            )
                else:
                    console.print(
                        f"  [{Colors.TEXT_TERTIARY}]Usage: /copy [sql|results|error][/{Colors.TEXT_TERTIARY}]\n"
                    )
                continue

            elif cmd in ("/rerun", "/retry"):
                if not last_nl_query:
                    console.print(
                        f"  [{Colors.TEXT_TERTIARY}]No previous query to rerun yet.[/{Colors.TEXT_TERTIARY}]\n"
                    )
                    continue
                console.print(
                    f"  [{Colors.AI_ACCENT}]{Icons.arrow()}[/{Colors.AI_ACCENT}] "
                    f"[bold]Rerunning:[/bold] [{Colors.TEXT_PRIMARY}]\"{last_nl_query}\"[/{Colors.TEXT_PRIMARY}]\n"
                )
                user_input = last_nl_query

            elif cmd == "/explain":
                if not last_sql and not last_error:
                    console.print(
                        f"  [{Colors.TEXT_TERTIARY}]No query or error to explain yet."
                        f"[/{Colors.TEXT_TERTIARY}]\n"
                    )
                elif last_sql:
                    from teshq.cli.ui.ai_context import print_ai_explanation
                    explanation = (
                        f"Query: \"{last_nl_query}\"\n"
                        f"SQL: {last_sql}\n"
                        f"Dialect: {last_dialect}"
                    )
                    if last_parameters:
                        explanation += f"\nParameters: {last_parameters}"
                    print_ai_explanation(explanation, title="Query Breakdown")
                    console.print()
                else:
                    from teshq.cli.ui.ai_context import print_ai_explanation
                    explanation = f"Query: \"{last_nl_query}\"\nError Encountered: {last_error}"
                    print_ai_explanation(explanation, title="Error Explanation")
                    console.print()
                continue

            elif cmd in ("/history", "/hist"):
                if not session_history:
                    console.print(
                        f"  [{Colors.TEXT_TERTIARY}]No commands executed in this session yet.[/{Colors.TEXT_TERTIARY}]\n"
                    )
                else:
                    console.print(
                        f"  [bold {Colors.PRIMARY}]{Icons.time()} Session Command History:[/bold {Colors.PRIMARY}]"
                    )
                    for idx, h_cmd in enumerate(session_history, 1):
                        console.print(f"    [dim]{idx}.[/dim] [{Colors.TEXT_PRIMARY}]{h_cmd}[/{Colors.TEXT_PRIMARY}]")
                    console.print()
                continue

            elif cmd == "/search":
                query = parts[1] if len(parts) > 1 else ""
                if not query:
                    console.print(
                        f"  [{Colors.TEXT_TERTIARY}]Usage: /search <text>[/{Colors.TEXT_TERTIARY}]\n"
                    )
                else:
                    matches = [h for h in session_history if query.lower() in h.lower()]
                    if matches:
                        console.print(f"  [bold {Colors.PRIMARY}]Matches for \"{query}\":[/bold {Colors.PRIMARY}]")
                        for m in matches:
                            console.print(f"    • [{Colors.TEXT_PRIMARY}]{m}[/{Colors.TEXT_PRIMARY}]")
                    else:
                        console.print(f"  [{Colors.TEXT_MUTED}]No matches found in session history for \"{query}\".[/{Colors.TEXT_MUTED}]")
                    console.print()
                continue

            else:
                console.print(
                    f"  [{Colors.WARNING}]{Icons.warn()} Unknown command:[/{Colors.WARNING}] "
                    f"'{cmd}' {Icons.separator()} Type "
                    f"[bold {Colors.PRIMARY}]/help[/bold {Colors.PRIMARY}] for commands.\n"
                )
                continue

        # ── Natural Language Query Execution ──────────────────────────
        try:
            if not engine:
                engine = TeshEngine(provider=provider_override)

            last_dialect = getattr(engine, "_dialect", "SQL") or "SQL"

            # Conversational multi-turn enrichment
            request_text = user_input
            follow_up_triggers = (
                "now ", "only ", "filter ", "sort ", "order by ",
                "group by ", "limit ", "also ", "and ",
            )
            if last_nl_query and any(
                user_input.lower().startswith(t) for t in follow_up_triggers
            ):
                request_text = (
                    f"Context from previous query '{last_nl_query}' "
                    f"with SQL: {last_sql}. Follow-up request: {user_input}"
                )

            # ── 6-stage live cognitive progress ───────────────────────
            stage_tracker = StageTracker(QUERY_STAGES, console=console)
            query_start = time.time()
            with stage_tracker:
                engine_result = engine.query(
                    request_text,
                    dry_run=False,
                    on_progress=stage_tracker.on_progress,
                )
            query_time = time.time() - query_start

            last_sql = engine_result.sql
            last_parameters = engine_result.parameters
            last_nl_query = user_input

            # Update session stats
            session_queries += 1
            total_ms = (
                engine_result.plan_latency_ms
                + engine_result.sql_latency_ms
                + engine_result.exec_latency_ms
            )
            session_total_time += total_ms / 1000.0
            session_total_tokens += engine_result.total_tokens

            # ── Build command block ───────────────────────────────────
            block = CommandBlock(user_input)

            # SQL
            block.set_sql(
                last_sql,
                dialect=last_dialect,
                parameters=last_parameters,
            )

            # Results
            result = QueryResult(
                results=engine_result.rows,
                query=last_sql,
                parameters=last_parameters,
                natural_language_query=user_input,
            )
            last_result = result

            if result and len(result) > 0:
                display_results = result.display_results
                headers = list(display_results[0].keys())
                rows = [[row[h] for h in headers] for row in display_results]

                results_panel = render_results_table(
                    headers=headers,
                    rows=rows,
                    title="Results",
                    summary=f"Found {len(result):,} record(s)",
                )
                # Extract the inner table from the panel
                block.set_results(results_panel, len(result))

            # Metrics
            block.set_metrics(
                total_ms=total_ms,
                total_tokens=engine_result.total_tokens,
                cost_usd=engine_result.cost_estimate_usd,
            )

            # Print the complete block
            block.print()

        except Exception as e:
            # Error block
            last_error = str(e)
            console.print()
            block = CommandBlock(user_input)
            block.set_error(str(e))
            block.print()
            print_error_card(e, context="Query Processing")
            console.print()
