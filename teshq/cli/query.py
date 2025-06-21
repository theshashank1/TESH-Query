import time
from pathlib import Path

import typer
from sqlalchemy.exc import SQLAlchemyError

from teshq.core.llm import SQLQueryGenerator
from teshq.core.query import execute_sql_query
from teshq.utils import get_database_url as get_db_url
from teshq.utils import get_gemini_config as get_gemini_credentials
from teshq.utils.formater import print_query_table
from teshq.utils.ui import (  # print_config,; print_header,; progress,; prompt,
    error,
    info,
    print_divider,
    print_sql,
    status,
    success,
)

app = typer.Typer()


@app.command(
    name="query",
    help="Execute the Natural Language Query on Database and return the result",
)
def process_nl_query(
    natural_language_request: str,
    save_csv: bool = typer.Option(False, "--save-csv", help="Save the query result as a CSV file.", show_default=True),
):
    """
    Processes a natural language query, generates SQL, executes it, and prints the results.
    """

    with status("Geting Required Keys", "Sucessfully Retrived the Required Keys"):
        # Simulate key retrieval delay
        time.sleep(1)
        gemini_api_key, gemini_model = get_gemini_credentials()
        generator = SQLQueryGenerator(api_key=gemini_api_key, model_name=gemini_model)
        db_url_val = get_db_url()
        db_display = db_url_val.split("@")[-1] if db_url_val and "@" in db_url_val else "default DB"

    schema_dir = Path("db_schema")
    schema_file_path = schema_dir / "schema.txt"

    info(f"📁 Loading schema from: [bold]{schema_file_path}[/bold]")
    try:
        schema = generator.load_schema(schema_file_path)
    except FileNotFoundError:
        error(f"❌ Schema file not found at: {schema_file_path}")
        raise typer.Exit(code=1)
    except Exception as e:
        error(f"❌ Failed to load schema: {e}")
        raise typer.Exit(code=1)

    info(f"🧠 Generating SQL for your query: “[italic]{natural_language_request}[/italic]”")
    try:
        result = generator.generate_sql(natural_language_request, schema)
    except Exception as e:
        error(f"❌ SQL generation failed: {e}")
        raise typer.Exit(code=1)

    with status("Generating SQL Query", "SQL Query Generated Successfully"):
        sql_query = result.get("query")
        parameters = result.get("parameters")

    if not sql_query:
        error("SQL generation did not return a valid query.")
        raise typer.Exit(code=1)

    print_sql(sql_query, title="Generated SQL Query")
    if parameters:
        info(f"🔧 Query parameters: {parameters}")

    info(f"🗃️  Executing query on database: [bold]{db_display}[/bold]")
    try:
        with status("Executing SQL Query", "SQL Query Executed Successfully"):
            query_execution_result = execute_sql_query(
                db_url=db_url_val,
                query=sql_query,
                parameters=parameters,
            )
    except SQLAlchemyError as e:
        error(f"❌ SQL execution failed: {e}")
        raise typer.Exit(code=1)

    success("✅ SQL query executed successfully!")
    print_divider()
    print_query_table(natural_language_request, sql_query, parameters, query_execution_result)
    success("🎉 Query processed and result displayed.")
