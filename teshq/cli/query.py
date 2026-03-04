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
from teshq.utils.cli_logging import CLILogger
from teshq.utils.config import get_database_url as get_db_url
from teshq.utils.output import QueryResult
from teshq.utils.save import save_to_csv, save_to_excel, save_to_sqlite
from teshq.telemetry.events import track_command, track_error, track_feature
from teshq.utils.ui import error, handle_error, info, print_divider, print_sql, status, success, warning
from teshq.utils.validation import CLIValidator, ValidationError

app = typer.Typer()

# Schema files: prefer ~/.teshq/schema/, fall back to local db_schema/
_SCHEMA_DIR = get_schema_path("schema.txt").parent
_TESHQ_SCHEMA_PATH = get_schema_path("schema.txt")       # default: compact minimal
_TESHQ_SCHEMA_FULL_PATH = get_schema_path("schema_full.txt")  # optional: full verbose
_LOCAL_SCHEMA_PATH = Path("db_schema") / "schema.txt"
_LOCAL_SCHEMA_FULL_PATH = Path("db_schema") / "schema_full.txt"

def save_results(
    df: pd.DataFrame,
    csv_path: str = None,
    excel_path: str = None,
    sqlite_path: str = None,
    sqlite_table: str = "results",
) -> str:
    """Saves the query results to the specified formats. Returns normalized excel_path."""
    if csv_path:
        save_to_csv(df, csv_path)
    if excel_path:
        if not excel_path.endswith((".xlsx", ".xls")):
            excel_path += ".xlsx"
        save_to_excel(df, excel_path)
    if sqlite_path:
        save_to_sqlite(df, sqlite_path, sqlite_table)
    return excel_path


@app.command(
    name="query",
    help="Run a natural language query against your database.",
)
def process_nl_query(
    natural_language_request: str = typer.Argument(..., help="What you want to know, in plain English."),
    save_csv: str = typer.Option(None, "--save-csv", metavar="FILE", help="Save results to a CSV file."),
    save_excel: str = typer.Option(None, "--save-excel", metavar="FILE", help="Save results to an Excel (.xlsx) file."),
    save_sqlite: str = typer.Option(None, "--save-sqlite", metavar="FILE", help="Save results to a SQLite database file."),
    full_schema: bool = typer.Option(
        False,
        "--full-schema",
        help="Use full verbose schema (schema_full.txt) for highest SQL accuracy. Requires prior: teshq db introspect --all",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Generate and validate SQL but do NOT execute it against the database.",
    ),
    explain: bool = typer.Option(
        False,
        "--explain",
        help="Print the query plan, selected tables, generated SQL, and execution time.",
    ),
    schema_preview: bool = typer.Option(
        False,
        "--schema-preview",
        help="Print the compressed schema that will be sent to the LLM, then exit.",
    ),
    log: bool = typer.Option(None, "--log", help="Write detailed logs to file."),
):
    """
    Convert a natural-language question into SQL and execute it.

    Examples:

      teshq query "show the top 10 customers by revenue"

      teshq query "how many orders were placed last month" --save-csv monthly_orders.csv
    """
    
    # Initialize CLI logger
    cli_logger = CLILogger("query")
    logging_active = cli_logger.setup_file_logging(log)

    # Track command invocation (privacy-safe: no query text)
    track_command(
        "query",
        save_csv=bool(save_csv),
        save_excel=bool(save_excel),
        save_sqlite=bool(save_sqlite),
    )

    # --schema-preview: print compressed schema and exit (no LLM needed)
    if schema_preview:
        try:
            engine = TeshEngine()
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
                "log": log
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

        with status("Initializing Engine", "Engine ready"):
                db_url_val = get_db_url()
                engine = TeshEngine(db_url=db_url_val)

        if dry_run:
            info("🧠 Generating SQL in dry-run mode (no execution)...")
        else:
            db_display = db_url_val.split("@")[-1] if db_url_val and "@" in db_url_val else "database"
            info(f"🧠 Generating and executing query on [bold]{db_display}[/bold]...")

        engine_result = engine.query(natural_language_request, dry_run=dry_run)
            
        if not engine_result.success:
            error(f"❌ Query generation/execution failed: {engine_result.error}")
            raise typer.Exit(code=1)

        sql_query, parameters = engine_result.sql, engine_result.parameters
        
        print_sql(sql_query, title="Generated SQL Query")

        if parameters:
            info(f"🔧 Query parameters: {parameters}")

        if dry_run:
            success("✅ SQL generated. Dry-run complete — query was NOT executed.")
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

        success("✅ SQL query executed successfully!")
        print_divider()

        if explain:
            info(f"📊 Explain:\n  SQL: {sql_query}\n  Parameters: {parameters}")
        
        # Use the unified output system for consistent display
        result.print_query_table()

        # Log query execution
        if logging_active:
            cli_logger.log_query_execution(
                query=sql_query,
                parameters=parameters,
                row_count=len(result),
                execution_time_ms=0  # This would be captured in run_sql_query
            )

        # Show token usage summary for this query (from engine result)
        info(f"🏷️  Token usage: {engine_result.total_tokens:,} tokens, estimated cost: ${engine_result.cost_estimate_usd:.4f}")
        info(f"⏱️  Latency: {engine_result.plan_latency_ms + engine_result.sql_latency_ms + engine_result.exec_latency_ms}ms (Plan: {engine_result.plan_latency_ms}ms, SQL: {engine_result.sql_latency_ms}ms, Exec: {engine_result.exec_latency_ms}ms)")

        # Save results if requested - use the normalized DataFrame
        if result is not None and (save_csv or save_excel or save_sqlite):
            if len(result) == 0:
                warning("⚠️  Query returned 0 rows — saving empty result set.")
            df = result.dataframe
            save_excel = save_results(df, save_csv, save_excel, save_sqlite)

            # Track feature usage
            for fmt, path in [("save_csv", save_csv), ("save_excel", save_excel), ("save_sqlite", save_sqlite)]:
                if path:
                    track_feature(fmt)

            # Log file operations
            if logging_active:
                for save_path, format_name in [(save_csv, "CSV"), (save_excel, "Excel"), (save_sqlite, "SQLite")]:
                    if save_path:
                        try:
                            file_size = Path(save_path).stat().st_size if Path(save_path).exists() else None
                            cli_logger.log_file_operation(f"Save {format_name}", save_path, True, file_size)
                        except Exception:
                            cli_logger.log_file_operation(f"Save {format_name}", save_path, False)

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
        handle_error(
            e,
            "Schema file not found",
            suggest_action=(
                "Run 'teshq introspect' first, or ensure the schema file exists at "
                "~/.teshq/schema/schema.txt"
            ),
        )
        raise typer.Exit(1)
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
