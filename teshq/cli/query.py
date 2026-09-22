import time
import warnings
from pathlib import Path

import pandas as pd

# Suppress annoying Pydantic/LangChain warnings that interfere with the rich console UI
warnings.filterwarnings("ignore", category=UserWarning)

import typer
from sqlalchemy.exc import SQLAlchemyError

from teshq.config.paths import get_schema_path
from teshq.core.engine import TeshEngine
from teshq.cli.logging import CLILogger
from teshq.config.loader import get_database_url as get_db_url
from teshq.utils.output import QueryResult
from teshq.utils.save import save_to_csv, save_to_excel, save_to_sqlite, resolve_output_path
from teshq.telemetry.events import track_command, track_error, track_feature
from teshq.cli.ui import Colors, error, handle_error, info, print_divider, print_metrics, print_sql_card, status, success, tip, warning
from teshq.core.exceptions import TeshqConfigurationError
from teshq.core.validation import CLIValidator, ValidationError

app = typer.Typer()

# Schema path constants - resolved lazily at runtime by TeshEngine
# (kept for --schema-preview feature only)
def _get_schema_path(filename: str):
    """Lazily resolve schema path to avoid import-time failures."""
    return get_schema_path(filename)

def save_results(
    df: pd.DataFrame,
    csv_path: str = None,
    excel_path: str = None,
    sqlite_path: str = None,
    sqlite_table: str = "results",
    query_text: str = None,
) -> dict:
    """Saves the query results to the specified formats.

    Returns a dict mapping format names to their resolved display paths.
    """
    saved = {}
    if csv_path:
        resolved, display = resolve_output_path(query_text=query_text, ext="csv", custom_path=csv_path)
        resolved_str = str(resolved)
        if not resolved_str.endswith(".csv"):
            resolved_str += ".csv"
        save_to_csv(df, resolved_str)
        saved["csv"] = display
    if excel_path:
        resolved, display = resolve_output_path(query_text=query_text, ext="xlsx", custom_path=excel_path)
        resolved_str = str(resolved)
        if not resolved_str.endswith((".xlsx", ".xls")):
            resolved_str += ".xlsx"
        save_to_excel(df, resolved_str)
        saved["excel"] = display
    if sqlite_path:
        resolved, display = resolve_output_path(query_text=query_text, ext="db", custom_path=sqlite_path)
        resolved_str = str(resolved)
        if not resolved_str.endswith((".db", ".sqlite", ".sqlite3")):
            resolved_str += ".db"
        save_to_sqlite(df, resolved_str, sqlite_table)
        saved["sqlite"] = display
    return saved


PANEL_EXPORT = "📤 Export & Output Files"
PANEL_EXECUTION = "⚡ Execution & Query Controls"
PANEL_ROUTING = "🤖 Model & Inference Routing"
PANEL_DIAGNOSTICS = "⚙️ Diagnostics & Logging"


@app.command(
    name="query",
    help="Run a natural language query against your database.",
)
def process_nl_query(
    natural_language_request: str = typer.Argument(
        None,
        help="What you want to know, in plain English. (Prompts interactively if omitted)",
    ),
    save_csv: str = typer.Option(
        None, "--save-csv", metavar="FILE",
        help="Save results to CSV [default: .teshq/outputs/<query_slug>_<timestamp>.csv]",
        rich_help_panel=PANEL_EXPORT,
    ),
    save_excel: str = typer.Option(
        None, "--save-excel", metavar="FILE",
        help="Save results to an Excel spreadsheet (.xlsx)",
        rich_help_panel=PANEL_EXPORT,
    ),
    save_sqlite: str = typer.Option(
        None, "--save-sqlite", metavar="FILE",
        help="Save results to a SQLite database file",
        rich_help_panel=PANEL_EXPORT,
    ),
    limit: int = typer.Option(
        None, "--limit", "-n", metavar="N",
        help="Limit results to N rows (adds LIMIT to SQL)",
        rich_help_panel=PANEL_EXECUTION,
    ),
    confirm_run: bool = typer.Option(
        False, "--confirm", "-i",
        help="Interactively review and confirm generated SQL before running it",
        rich_help_panel=PANEL_EXECUTION,
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Generate and validate SQL without executing it against the database",
        rich_help_panel=PANEL_EXECUTION,
    ),
    explain: bool = typer.Option(
        False, "--explain",
        help="Print the query plan, selected tables, generated SQL, and execution time",
        rich_help_panel=PANEL_EXECUTION,
    ),
    schema_preview: bool = typer.Option(
        False, "--schema-preview",
        help="Print the compressed schema that will be sent to the LLM, then exit",
        rich_help_panel=PANEL_EXECUTION,
    ),
    full_schema: bool = typer.Option(
        False, "--full-schema",
        help="Use full schema (schema_full.txt) with row counts and indexes",
        rich_help_panel=PANEL_EXECUTION,
    ),
    local: bool = typer.Option(
        False, "--local",
        help="Force local GGUF model inference",
        rich_help_panel=PANEL_ROUTING,
    ),
    cloud: bool = typer.Option(
        False, "--cloud",
        help="Force cloud model inference (Gemini or Azure OpenAI)",
        rich_help_panel=PANEL_ROUTING,
    ),
    verbose: bool = typer.Option(
        None, "--verbose",
        help="Write detailed logs to ~/.teshq/logs/",
        rich_help_panel=PANEL_DIAGNOSTICS,
    ),
):
    """
    Convert a natural-language question into SQL and execute it.

    Beginners:
      • Run 'teshq query' for an interactive prompt.
      • Run 'teshq query -i "your question"' to review SQL before execution.

    Power Users & Scripting:
      • Pass direct questions and output flags:
        teshq query "top 10 customers by revenue" --save-csv top10.csv
        teshq query "orders placed last month" --dry-run
    """
    import sys
    from teshq.utils.ui import prompt

    # Interactive fallback if natural_language_request is omitted
    if not natural_language_request:
        if sys.stdin.isatty():
            try:
                natural_language_request = prompt("What would you like to know from your database?")
            except (KeyboardInterrupt, typer.Abort):
                raise typer.Exit(0)
            if not natural_language_request or not natural_language_request.strip():
                tip("No query provided. Run 'teshq query \"your question\"' or 'teshq chat' for interactive mode.")
                raise typer.Exit(0)
        else:
            error("Missing argument 'NATURAL_LANGUAGE_REQUEST'.")
            tip("Usage: teshq query \"your question\"")
            raise typer.Exit(1)

    # Initialize CLI logger
    cli_logger = CLILogger("query")
    logging_active = cli_logger.setup_file_logging(verbose)

    # Validate mutually exclusive options
    if local and cloud:
        error("Cannot use both --local and --cloud simultaneously.")
        raise typer.Exit(1)

    # Track command invocation (privacy-safe: no query text)
    track_command(
        "query",
        save_csv=bool(save_csv),
        save_excel=bool(save_excel),
        save_sqlite=bool(save_sqlite),
        local=local,
    )

    # Resolve provider override
    provider_override = None
    if local:
        provider_override = "local"
    elif cloud:
        from teshq.config.loader import get_settings
        s = get_settings()
        provider_override = "azure" if s.azure_openai_api_key and s.llm_provider.lower() == "azure" else "google"

    # --schema-preview: print compressed schema and exit (no LLM needed)
    if schema_preview:
        try:
            engine = TeshEngine(provider=provider_override)
            preview = engine.get_schema_preview(natural_language_request)
            info("📋 Compressed schema sent to LLM:")
            from rich.console import Console

            Console().print(preview)
        except Exception as e:
            handle_error(e, "Schema Preview", show_traceback=True)
            raise typer.Exit(code=1)
        raise typer.Exit(code=0)

    start_time = time.time()
    
    try:
        # Log command start
        if logging_active:
            cli_logger.log_command_start({
                "natural_language_request": natural_language_request,
                "save_csv": save_csv,
                "save_excel": save_excel,
                "save_sqlite": save_sqlite,
                "local": local,
                "cloud": cloud,
                "verbose": verbose
            })
        
        # Validate natural language query
        is_valid, validation_message = CLIValidator.validate_natural_language_query(natural_language_request)
        if not is_valid:
            if logging_active:
                cli_logger.log_error("Query validation failed", validation_message)
            handle_error(
                ValidationError(validation_message, "natural_language_query"),
                "Query Validation",
                suggest_action="Please provide a valid natural language query (3-1000 characters)",
            )
            raise typer.Exit(1)

        # Extension appending is now handled by resolve_output_path + save_results
        # We still validate user-provided save paths if they have directory components

        # Validate save paths if provided
        save_options = [(save_csv, "csv"), (save_excel, "excel"), (save_sqlite, "sqlite")]

        for save_path, format_type in save_options:
            if save_path:
                is_valid, validation_message = CLIValidator.validate_save_path(save_path, format_type)
                if not is_valid:
                    if logging_active:
                        cli_logger.log_error(f"Save path validation failed for {format_type}", validation_message)
                    handle_error(
                        ValidationError(validation_message, f"save_{format_type}"),
                        "Save Path Validation",
                        suggest_action=f"Please provide a valid {format_type} file path",
                    )
                    raise typer.Exit(1)

        with status("Initializing TESH Engine...", "Engine ready"):
            db_url_val = get_db_url()
            engine = TeshEngine(db_url=db_url_val, provider=provider_override)

        dialect_name = getattr(engine, "_dialect", "SQL") or "SQL"

        # If confirm_run is requested, synthesize SQL first and ask for review
        if confirm_run and not dry_run:
            with status("Synthesizing SQL query...") as s:
                def _prog_dry(idx, name, detail=None):
                    msg = f"[{Colors.PRIMARY}]{name}[/{Colors.PRIMARY}]" + (f" [dim italic]({detail})[/dim italic]" if detail else "")
                    if hasattr(s, "update"): s.update(msg)
                engine_result = engine.query(natural_language_request, dry_run=True, on_progress=_prog_dry)
            sql_query, parameters = engine_result.sql, engine_result.parameters
            print_sql_card(sql_query, dialect=dialect_name, parameters=parameters, title="Generated SQL Query")
            
            from rich.prompt import Confirm
            try:
                should_run = Confirm.ask(f"[bold {Colors.WARNING}]Execute this query against your database?[/bold {Colors.WARNING}]", default=True)
            except KeyboardInterrupt:
                warning("\nExecution cancelled.")
                raise typer.Exit(code=0)
            if not should_run:
                warning("Execution cancelled by user.")
                raise typer.Exit(code=0)
            
            with status("Executing query against database...") as s:
                def _prog_exec(idx, name, detail=None):
                    msg = f"[{Colors.PRIMARY}]{name}[/{Colors.PRIMARY}]" + (f" [dim italic]({detail})[/dim italic]" if detail else "")
                    if hasattr(s, "update"): s.update(msg)
                engine_result = engine.query(natural_language_request, dry_run=False, on_progress=_prog_exec)
        else:
            db_display = db_url_val.split("@")[-1] if db_url_val and "@" in db_url_val else "database"
            status_msg = "Synthesizing SQL (dry-run)..." if dry_run else f"Processing query on {db_display}..."
            with status(status_msg) as s:
                def _prog(idx, name, detail=None):
                    msg = f"[{Colors.PRIMARY}]{name}[/{Colors.PRIMARY}]" + (f" [dim italic]({detail})[/dim italic]" if detail else "")
                    if hasattr(s, "update"): s.update(msg)
                engine_result = engine.query(natural_language_request, dry_run=dry_run, on_progress=_prog)

            sql_query, parameters = engine_result.sql, engine_result.parameters
            print_sql_card(sql_query, dialect=dialect_name, parameters=parameters, title="Generated SQL Query")

        if dry_run:
            success("SQL generated. Dry-run complete — query was NOT executed.")
            if explain and engine_result.plan:
                info(f"📊 Explain:\n  Tables: {engine_result.plan.tables}\n  Filters: {engine_result.plan.filters}\n  SQL: {sql_query}\n  Parameters: {parameters}")
            raise typer.Exit(code=0)

        # Wrap Engine result in the UI QueryResult formatter
        result = QueryResult(
            results=engine_result.rows,
            query=sql_query,
            parameters=parameters,
            natural_language_query=natural_language_request
        )

        if explain:
            info(f"📊 Explain:\n  SQL: {sql_query}\n  Parameters: {parameters}")
        
        # Use the unified output system for consistent display
        result.print_query_table()

        # Telemetry metrics panel
        print_metrics(
            plan_latency_ms=engine_result.plan_latency_ms,
            sql_latency_ms=engine_result.sql_latency_ms,
            exec_latency_ms=engine_result.exec_latency_ms,
            total_tokens=engine_result.total_tokens,
            cost_estimate_usd=engine_result.cost_estimate_usd,
            row_count=len(result),
        )

        # Log query execution with real latency
        if logging_active:
            cli_logger.log_query_execution(
                query=sql_query,
                parameters=parameters,
                row_count=len(result),
                execution_time_ms=engine_result.exec_latency_ms
            )

        # Save results if requested - use the normalized DataFrame
        if result is not None and (save_csv or save_excel or save_sqlite):
            if len(result) == 0:
                warning("⚠️  Query returned 0 rows — saving empty result set.")
            df = result.dataframe
            saved_paths = save_results(
                df, save_csv, save_excel, save_sqlite,
                query_text=natural_language_request,
            )

            # Track feature usage
            for fmt_key in ("csv", "excel", "sqlite"):
                if fmt_key in saved_paths:
                    track_feature(f"save_{fmt_key}")

            # Show saved paths to user
            for fmt_key, display in saved_paths.items():
                success(f"  Saved {fmt_key.upper()} → {display}")

            # Log file operations
            if logging_active:
                for fmt_key, display in saved_paths.items():
                    try:
                        file_size = Path(display).stat().st_size if Path(display).exists() else None
                        cli_logger.log_file_operation(f"Save {fmt_key.upper()}", display, True, file_size)
                    except Exception:
                        cli_logger.log_file_operation(f"Save {fmt_key.upper()}", display, False)

        success("🎉 Query processed and result displayed.")
        
        # Log successful completion
        if logging_active:
            duration = time.time() - start_time
            cli_logger.log_command_end(True, duration, row_count=len(result) if result else 0)

    except ValidationError as e:
        track_error("query", "ValidationError")
        if logging_active:
            duration = time.time() - start_time
            cli_logger.log_command_end(False, duration, error=str(e), error_type="ValidationError")
        handle_error(e, "Validation error", suggest_action="Check your query text and save paths.")
        raise typer.Exit(1)
    except SQLAlchemyError as e:
        track_error("query", "SQLAlchemyError")
        if logging_active:
            duration = time.time() - start_time
            cli_logger.log_command_end(False, duration, error=str(e), error_type="SQLAlchemyError")
        handle_error(e, "Database error", suggest_action="Check your database connection and query syntax.")
        raise typer.Exit(1)
    except FileNotFoundError as e:
        track_error("query", "FileNotFoundError")
        if logging_active:
            duration = time.time() - start_time
            cli_logger.log_command_end(False, duration, error=str(e), error_type="FileNotFoundError")
        if "Local GGUF model not found" in str(e):
            handle_error(
                e,
                "Local model not found",
                suggest_action="Run 'teshq model pull' first, or configure a valid path.",
            )
        else:
            handle_error(
                e,
                "Schema file not found",
                suggest_action=(
                    "Run 'teshq introspect' first, or ensure the schema file exists at "
                    "~/.teshq/schema/schema.txt"
                ),
            )
        raise typer.Exit(1)
    except ImportError as e:
        track_error("query", "ImportError")
        if logging_active:
            duration = time.time() - start_time
            cli_logger.log_command_end(False, duration, error=str(e), error_type="ImportError")
        
        handle_error(
            e,
            "Missing Dependencies",
            suggest_action="To use the local GGUF backend, you must install the optional dependencies. Run: pip install teshq[local]"
        )
        raise typer.Exit(1)
    except TeshqConfigurationError as e:
        track_error("query", "TeshqConfigurationError")
        if logging_active:
            duration = time.time() - start_time
            cli_logger.log_command_end(False, duration, error=str(e), error_type="TeshqConfigurationError")
            
        handle_error(
            e,
            "Configuration Error",
            suggest_action="Ensure your DATABASE_URL and other required settings are properly configured."
        )
        raise typer.Exit(1)
    except typer.Exit:
        raise
    except KeyboardInterrupt:
        warning("\nQuery cancelled.")
        raise typer.Exit(0)
    except Exception as e:
        track_error("query", type(e).__name__)
        if logging_active:
            duration = time.time() - start_time
            cli_logger.log_command_end(False, duration, error=str(e), error_type=type(e).__name__)
        handle_error(e, "Query processing error", show_traceback=True, suggest_action="Please check your input and try again.")
        raise typer.Exit(1)
    finally:
        # Cleanup logger
        if logging_active:
            cli_logger.cleanup()
