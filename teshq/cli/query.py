import time
from pathlib import Path
from typing import Optional

import pandas as pd
import typer
from sqlalchemy.exc import SQLAlchemyError

from teshq.core.llm import SQLQueryGenerator
from teshq.core.query import execute_sql_query
from teshq.utils.config import get_database_url as get_db_url
from teshq.utils.config import get_gemini_config as get_gemini_credentials
from teshq.utils.config import get_storage_paths
from teshq.utils.formater import print_query_table
from teshq.utils.logging import configure_global_logger
from teshq.utils.save import save_to_csv, save_to_excel, save_to_sqlite
from teshq.utils.ui import error, handle_error, info, print_divider, print_sql, status, success
from teshq.utils.validation import CLIValidator, ValidationError

app = typer.Typer()


def get_llm_generator() -> SQLQueryGenerator:
    """Initializes and returns the SQLQueryGenerator."""
    gemini_api_key, gemini_model = get_gemini_credentials()
    return SQLQueryGenerator(api_key=gemini_api_key, model_name=gemini_model)


def load_db_schema(generator: SQLQueryGenerator, schema_path: Path):
    """Loads the database schema from the specified path."""
    info(f"📁 Loading schema from: [bold]{schema_path}[/bold]")
    try:
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found at: {schema_path}")
        return generator.load_schema(schema_path)
    except FileNotFoundError as e:
        handle_error(
            e,
            "Database Schema Not Found",
            suggest_action="Try running `teshq introspect` to generate the schema file.",
            show_traceback=False,
        )
        raise typer.Exit(code=1)
    except Exception as e:
        handle_error(e, "Failed to Load Schema", show_traceback=True)
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


def run_sql_query(db_url: str, sql_query: str, parameters: dict):
    """Executes the SQL query against the database."""
    db_display = db_url.split("@")[-1] if db_url and "@" in db_url else "default DB"
    info(f"🗃️  Executing query on database: [bold]{db_display}[/bold]")
    try:
        with status("Executing SQL Query", "SQL Query Executed Successfully"):
            return execute_sql_query(db_url=db_url, query=sql_query, parameters=parameters)
    except SQLAlchemyError as e:
        error(f"❌ SQL execution failed: {e}")
        raise typer.Exit(code=1)


def save_results(
    df: pd.DataFrame,
    csv_path: Optional[Path] = None,
    excel_path: Optional[Path] = None,
    sqlite_path: Optional[Path] = None,
    sqlite_table: str = "results",
    check_existing: bool = True,
):
    """
    Saves the query results to the specified formats.

    Args:
        df: DataFrame to save
        csv_path: Path to save CSV file
        excel_path: Path to save Excel file
        sqlite_path: Path to save SQLite database
        sqlite_table: Table name for SQLite
        check_existing: Whether to check for existing files and prompt (default True)
    """
    from teshq.utils.ui import confirm, warning

    # Check for existing files and prompt for confirmation (if enabled)
    if check_existing:
        existing_files = []
        if csv_path and csv_path.exists():
            existing_files.append(str(csv_path))
        if excel_path and excel_path.exists():
            existing_files.append(str(excel_path))
        if sqlite_path and sqlite_path.exists():
            existing_files.append(str(sqlite_path))

        if existing_files:
            warning("⚠️  The following file(s) already exist:")
            for file in existing_files:
                info(f"  • {file}")

            if not confirm("Do you want to overwrite the existing file(s)?", default=False, danger=True):
                info("Save operation cancelled by user")
                raise typer.Exit(0)

    # Proceed with saving
    if csv_path:
        save_to_csv(df, str(csv_path))
    if excel_path:
        save_to_excel(df, str(excel_path))
    if sqlite_path:
        save_to_sqlite(df, str(sqlite_path), sqlite_table)


@app.command(
    name="query",
    help="Execute a Natural Language Query on the Database and return the result",
)
def process_nl_query(
    natural_language_request: str = typer.Argument(..., help="The natural language query to execute."),
    output_base_name: Optional[str] = typer.Argument(
        None, help="Base name for output files (required if any --save flag is used)."
    ),
    save_csv: bool = typer.Option(False, "--save-csv", help="Save the query result as a CSV file."),
    save_excel: bool = typer.Option(False, "--save-excel", help="Save the query result as an Excel file."),
    save_sqlite: bool = typer.Option(False, "--save-sqlite", help="Save the query result to a SQLite database."),
    log: bool = typer.Option(
        False, "--log", help="Enable real-time logging output to CLI (logs are always saved to file)."
    ),
):
    """
    Processes a natural language query, generates SQL, executes it, and prints the results.
    """
    storage_paths = get_storage_paths()

    # Ensure critical directories exist before using them
    storage_paths.metrics.mkdir(parents=True, exist_ok=True)
    storage_paths.query_results.mkdir(parents=True, exist_ok=True)
    storage_paths.schema.mkdir(parents=True, exist_ok=True)

    configure_global_logger(
        enable_cli_output=log,
        log_file_path=storage_paths.metrics / "teshq.log",
    )

    try:
        # Validate natural language query
        is_valid, validation_message = CLIValidator.validate_natural_language_query(natural_language_request)
        if not is_valid:
            handle_error(
                ValidationError(validation_message, "natural_language_query"),
                "Query Validation",
                suggest_action="Please provide a valid natural language query (3-1000 characters)",
            )
            raise typer.Exit(1)

        save_flags_used = save_csv or save_excel or save_sqlite
        if save_flags_used and not output_base_name:
            error("An output base name is required when using --save-csv, --save-excel, or --save-sqlite.")
            raise typer.Exit(1)

        # Check for existing files BEFORE using LLM credits
        if save_flags_used:
            # Determine output paths
            if output_base_name:
                user_path = Path(output_base_name)
                if user_path.is_absolute() or str(output_base_name).startswith("."):
                    base_output_path = user_path
                else:
                    base_output_path = storage_paths.query_results / output_base_name
            else:
                base_output_path = storage_paths.query_results / "query_result"

            # Validate parent directory
            output_dir = base_output_path.parent
            if not output_dir.exists():
                error(f"Output directory '{output_dir}' does not exist.")
                raise typer.Exit(1)

            # Check for existing files
            csv_path = base_output_path.with_suffix(".csv") if save_csv else None
            excel_path = base_output_path.with_suffix(".xlsx") if save_excel else None
            sqlite_path = base_output_path.with_suffix(".db") if save_sqlite else None

            existing_files = []
            if csv_path and csv_path.exists():
                existing_files.append(str(csv_path))
            if excel_path and excel_path.exists():
                existing_files.append(str(excel_path))
            if sqlite_path and sqlite_path.exists():
                existing_files.append(str(sqlite_path))

            if existing_files:
                from teshq.utils.ui import confirm, prompt, warning
                warning("⚠️  The following file(s) already exist:")
                for file in existing_files:
                    info(f"  • {file}")

                overwrite = confirm("Do you want to overwrite the existing file(s)?", default=False, danger=True)

                if not overwrite:
                    # Ask if user wants to rename
                    if confirm("Would you like to use a different filename?", default=True):
                        new_name = prompt("Enter new base filename", default=output_base_name)
                        # Update the base path with new name
                        if user_path.is_absolute() or str(output_base_name).startswith("."):
                            base_output_path = Path(new_name)
                        else:
                            base_output_path = storage_paths.query_results / new_name

                        # Update paths with new name
                        csv_path = base_output_path.with_suffix(".csv") if save_csv else None
                        excel_path = base_output_path.with_suffix(".xlsx") if save_excel else None
                        sqlite_path = base_output_path.with_suffix(".db") if save_sqlite else None

                        info(f"✓ Will save to: {base_output_path.name}")
                    else:
                        info("Save operation cancelled by user")
                        raise typer.Exit(0)
        else:
            # No save flags, these will be None
            csv_path = None
            excel_path = None
            sqlite_path = None

        with status("Initializing", "Initialization Complete"):
            time.sleep(1)
            generator = get_llm_generator()
            db_url_val = get_db_url()

        schema_file_path = storage_paths.schema / "schema.txt"
        schema = load_db_schema(generator, schema_file_path)

        sql_query, parameters = generate_sql_query(generator, natural_language_request, schema)
        print_sql(sql_query, title="Generated SQL Query")

        if parameters:
            info(f"🔧 Query parameters: {parameters}")

        query_execution_result = run_sql_query(db_url_val, sql_query, parameters)

        success("✅ SQL query executed successfully!")
        print_divider()
        print_query_table(natural_language_request, sql_query, parameters, query_execution_result)

        # Saving results if applicable
        if query_execution_result and save_flags_used:
            df = pd.DataFrame(query_execution_result)

            # Paths were already determined and checked before LLM execution
            # No need to check for existing files again - just save directly
            if csv_path:
                save_to_csv(df, str(csv_path))
            if excel_path:
                save_to_excel(df, str(excel_path))
            if sqlite_path:
                save_to_sqlite(df, str(sqlite_path), sqlite_table="results")

            if any([csv_path, excel_path, sqlite_path]):
                saved_files = [str(p) for p in [csv_path, excel_path, sqlite_path] if p]
                success(f"💾 Results saved to: {', '.join(saved_files)}")

        success("🎉 Query processed and result displayed successfully.")

    except SQLAlchemyError as e:
        handle_error(e, "Database Query Execution", suggest_action="Check your database connection and query syntax.")
        raise typer.Exit(1)
    except FileNotFoundError as e:
        # This is now less likely to be hit directly for schema, but good to keep.
        handle_error(
            e, "File Operation", suggest_action="Ensure all required files exist and paths are correctly set up."
        )
        raise typer.Exit(1)
    except Exception as e:
        handle_error(
            e, "Query Processing", show_traceback=True, suggest_action="Please check your input and try again."
        )
        raise typer.Exit(1)
