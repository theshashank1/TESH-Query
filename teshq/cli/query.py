import time
from pathlib import Path

import pandas as pd
import typer
from sqlalchemy.exc import SQLAlchemyError

from teshq.core.llm import SQLQueryGenerator
from teshq.core.query import execute_sql_query
from teshq.utils.config import get_database_url as get_db_url
from teshq.utils.config import get_gemini_config as get_gemini_credentials
from teshq.utils.formater import print_query_table
from teshq.utils.logging import configure_global_logger
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
    csv_path: str = None,
    excel_path: str = None,
    sqlite_path: str = None,
    sqlite_table: str = "results",
):
    """Saves the query results to the specified formats."""
    if csv_path:
        save_to_csv(df, csv_path)
    if excel_path:
        save_to_excel(df, excel_path)
    if sqlite_path:
        save_to_sqlite(df, sqlite_path, sqlite_table)


@app.command(
    name="query",
    help="Execute the Natural Language Query on Database and return the result",
)
def process_nl_query(
    natural_language_request: str = typer.Argument(..., help="The natural language query to execute."),
    output_base_name: str = typer.Argument(None, help="Base name for output files (required if any --save flag is used)."),
    save_csv: bool = typer.Option(False, "--save-csv", help="Save the query result as a CSV file."),
    save_excel: bool = typer.Option(False, "--save-excel", help="Save the query result as an Excel file."),
    save_sqlite: bool = typer.Option(False, "--save-sqlite", help="Save the query result to a SQLite database."),
    log: bool = typer.Option(False, "--log", help="Enable real-time logging output to CLI (logs are always saved to file)."),
):
    """
    Processes a natural language query, generates SQL, executes it, and prints the results.
    """
    # Configure logging based on --log flag
    configure_global_logger(enable_cli_output=log)

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

        # Check if a save flag is used and if an output name is provided
        save_flags_used = save_csv or save_excel or save_sqlite
        if save_flags_used and not output_base_name:
            error("An output base name is required when using --save-csv, --save-excel, or --save-sqlite.")
            raise typer.Exit(1)

        # Validate output directory if a save path is provided
        if output_base_name:
            output_path = Path(output_base_name)
            output_dir = output_path.parent
            if not output_dir.exists():
                error(f"Output directory '{output_dir}' does not exist.")
                raise typer.Exit(1)
            if not output_dir.is_dir():
                error(f"Output path '{output_dir}' is not a directory.")
                raise typer.Exit(1)

        with status("Initializing", "Initialization Complete"):
            time.sleep(1)
            generator = get_llm_generator()
            db_url_val = get_db_url()

        schema_dir = Path("db_schema")
        schema_file_path = schema_dir / "schema.txt"
        schema = load_db_schema(generator, schema_file_path)

        sql_query, parameters = generate_sql_query(generator, natural_language_request, schema)
        print_sql(sql_query, title="Generated SQL Query")

        if parameters:
            info(f"🔧 Query parameters: {parameters}")

        query_execution_result = run_sql_query(db_url_val, sql_query, parameters)

        success("✅ SQL query executed successfully!")
        print_divider()
        print_query_table(natural_language_request, sql_query, parameters, query_execution_result)

        if query_execution_result:
            df = pd.DataFrame(query_execution_result)
            csv_path = f"{output_base_name}.csv" if save_csv else None
            excel_path = f"{output_base_name}.xlsx" if save_excel else None
            sqlite_path = f"{output_base_name}.db" if save_sqlite else None
            save_results(df, csv_path, excel_path, sqlite_path)

            # Add a confirmation message if any file was saved
            if any([csv_path, excel_path, sqlite_path]):
                saved_files = []
                if csv_path:
                    saved_files.append(csv_path)
                if excel_path:
                    saved_files.append(excel_path)
                if sqlite_path:
                    saved_files.append(sqlite_path)
                success(f"💾 Results saved to: {', '.join(saved_files)}")

        success("🎉 Query processed and result displayed.")

    except SQLAlchemyError as e:
        handle_error(e, "Database Query Execution", suggest_action="Check your database connection and query syntax")
        raise typer.Exit(1)
    except FileNotFoundError as e:
        handle_error(e, "File Operation", suggest_action="Ensure all required files exist and schema is properly configured")
        raise typer.Exit(1)
    except Exception as e:
        handle_error(e, "Query Processing", show_traceback=True, suggest_action="Please check your input and try again")
        raise typer.Exit(1)
