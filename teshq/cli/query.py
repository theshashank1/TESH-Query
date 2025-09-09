import time
from pathlib import Path

import pandas as pd
import typer
from sqlalchemy.exc import SQLAlchemyError

from teshq.core.llm import SQLQueryGenerator
from teshq.core.query import execute_sql_query
from teshq.utils.cli_logging import CLILogger
from teshq.utils.config import get_database_url as get_db_url
from teshq.utils.config import get_gemini_config as get_gemini_credentials
from teshq.utils.output import QueryResult
from teshq.utils.save import save_to_csv, save_to_excel, save_to_sqlite
from teshq.utils.ui import error, handle_error, info, print_divider, print_sql, status, success
from teshq.utils.validation import CLIValidator, ValidationError

app = typer.Typer()


def get_llm_generator():
    """Initializes and returns the SQLQueryGenerator."""
    gemini_api_key, gemini_model = get_gemini_credentials()
    return SQLQueryGenerator(api_key=gemini_api_key, model_name=gemini_model)


def load_db_schema(generator: SQLQueryGenerator, schema_path: Path):
    """Loads the database schema from the specified path."""
    info(f"📁 Loading schema from: [bold]{schema_path}[/bold]")
    try:
        return generator.load_schema(schema_path)
    except FileNotFoundError:
        error(f"❌ Schema file not found at: {schema_path}")
        raise typer.Exit(code=1)
    except Exception as e:
        error(f"❌ Failed to load schema: {e}")
        raise typer.Exit(code=1)


def generate_sql_query(generator: SQLQueryGenerator, nl_query: str, schema: str):
    """Generates an SQL query from a natural language query."""
    info(f"🧠 Generating SQL for your query: “[italic]{nl_query}[/italic]”")
    try:
        with status("Generating SQL Query", "SQL Query Generated Successfully"):
            result = generator.generate_sql(nl_query, schema)
            sql_query = result.get("query")
            parameters = result.get("parameters")

        if not sql_query:
            error("SQL generation did not return a valid query.")
            raise typer.Exit(code=1)
        return sql_query, parameters
    except Exception as e:
        error(f"❌ SQL generation failed: {e}")
        raise typer.Exit(code=1)


def run_sql_query(db_url: str, sql_query: str, parameters: dict) -> QueryResult:
    """Executes the SQL query against the database and returns a QueryResult object."""
    db_display = db_url.split("@")[-1] if db_url and "@" in db_url else "default DB"
    info(f"🗃️  Executing query on database: [bold]{db_display}[/bold]")
    try:
        with status("Executing SQL Query", "SQL Query Executed Successfully"):
            raw_results = execute_sql_query(db_url=db_url, query=sql_query, parameters=parameters)
            return QueryResult(raw_results, sql_query, parameters)
    except SQLAlchemyError as e:
        error(f"❌ SQL execution failed: {e}")
        raise typer.Exit(code=1)


def save_results(
    df: pd.DataFrame,
    csv_path: str = None,
    excel_path: str = None,
    sqlite_path: str = None,
    sqlite_table: str = "results",
):
    """Saves the query results to the specified formats."""
    if csv_path:
        save_to_csv(df, csv_path)
    if excel_path:
        if not excel_path.endswith((".xlsx", ".xls")):
            excel_path += ".xlsx"
        save_to_excel(df, excel_path)
    if sqlite_path:
        save_to_sqlite(df, sqlite_path, sqlite_table)


@app.command(
    name="query",
    help="Execute the Natural Language Query on Database and return the result",
)
def process_nl_query(
    natural_language_request: str = typer.Argument(..., help="The natural language query to execute."),
    save_csv: str = typer.Option(None, "--save-csv", help="Save the query result as a CSV file."),
    save_excel: str = typer.Option(None, "--save-excel", help="Save the query result as an Excel file."),
    save_sqlite: str = typer.Option(None, "--save-sqlite", help="Save the query result to a SQLite database."),
    log: bool = typer.Option(None, "--log", help="Enable logging to file (overrides config default)"),
):
    """
    Processes a natural language query, generates SQL, executes it, and prints the results.
    """
    
    # Initialize CLI logger
    cli_logger = CLILogger("query")
    logging_active = cli_logger.setup_file_logging(log)
    
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

        with status("Initializing", "Initialization Complete"):
            time.sleep(1)
            generator = get_llm_generator()
            db_url_val = get_db_url()
            
            if logging_active:
                cli_logger.log_info("Initialization complete", generator_model=generator.model_name)

        schema_dir = Path("db_schema")
        schema_file_path = schema_dir / "schema.txt"
        schema = load_db_schema(generator, schema_file_path)

        sql_query, parameters = generate_sql_query(generator, natural_language_request, schema)
        print_sql(sql_query, title="Generated SQL Query")

        if parameters:
            info(f"🔧 Query parameters: {parameters}")

        if logging_active:
            cli_logger.log_info("SQL generated", 
                              sql_query=sql_query[:200] + "..." if len(sql_query) > 200 else sql_query,
                              has_parameters=bool(parameters))

        result = run_sql_query(db_url_val, sql_query, parameters)

        success("✅ SQL query executed successfully!")
        print_divider()
        
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

        # Show token usage summary for this query
        from teshq.utils.token_tracking import get_token_tracker
        tracker = get_token_tracker()
        session_summary = tracker.get_session_summary()
        
        if session_summary['queries'] > 0:
            last_query = session_summary['queries_detail'][-1] if 'queries_detail' in session_summary else None
            if last_query:
                info(f"🏷️  Token usage: {last_query['tokens']:,} tokens, estimated cost: ${last_query['cost']:.4f}")
                if logging_active:
                    cli_logger.log_token_usage(last_query['tokens'], last_query['cost'], "gemini")
            info(f"📊 Session total: {session_summary['total_tokens']:,} tokens, ${session_summary['total_cost']:.4f} (across {session_summary['queries']} queries)")

        # Save results if requested - use the normalized DataFrame
        if result and (save_csv or save_excel or save_sqlite):
            df = result.dataframe
            save_results(df, save_csv, save_excel, save_sqlite)
            
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

    # except ValidationError as e:
    #     # Validation errors are already handled above
    #     raise
    except SQLAlchemyError as e:
        if logging_active:
            duration = time.time() - start_time
            cli_logger.log_command_end(False, duration, error=str(e), error_type="SQLAlchemyError")
        handle_error(e, "Database Query Execution", suggest_action="Check your database connection and query syntax")
        raise typer.Exit(1)
    except FileNotFoundError as e:
        if logging_active:
            duration = time.time() - start_time
            cli_logger.log_command_end(False, duration, error=str(e), error_type="FileNotFoundError")
        handle_error(e, "File Operation", suggest_action="Ensure all required files exist and schema is properly configured")
        raise typer.Exit(1)
    except Exception as e:
        if logging_active:
            duration = time.time() - start_time
            cli_logger.log_command_end(False, duration, error=str(e), error_type=type(e).__name__)
        handle_error(e, "Query Processing", show_traceback=True, suggest_action="Please check your input and try again")
        raise typer.Exit(1)
    finally:
        # Cleanup logger
        if logging_active:
            cli_logger.cleanup()
