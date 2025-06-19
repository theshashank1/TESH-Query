"""
Configuration Command for TESH-Query CLI

This command sets up TeshQ's database, Gemini API, and file storage configuration.
It uses the consolidated configuration utilities from teshq/utils/config.py that retrieve and save settings
with fallback priorities from environment variables, the .env file, and config.json.

If `--save` is used, the configuration (e.g., DATABASE_URL, GEMINI API key, file paths) is persisted
in .env and/or config.json through the save_config() function.
"""

import os
import sys
from getpass import getpass
from urllib.parse import quote_plus

import typer
from sqlalchemy.engine.url import make_url

from teshq.utils.config import (  # DEFAULT_FILE_STORE_PATH,; DEFAULT_OUTPUT_PATH,; get_config,
    DEFAULT_GEMINI_MODEL,
    get_config_with_source,
    save_config,
)
from teshq.utils.ui import print_config  # We'll implement our own fallback if this fails
from teshq.utils.ui import (  # handle_error,
    clear_screen,
    confirm,
    error,
    indent_context,
    info,
    print_divider,
    print_header,
    prompt,
    section,
    space,
    success,
    tip,
    warning,
)

app = typer.Typer()
SUPPORTED_DBS = ["postgresql", "mysql", "sqlite"]


def display_current_config():
    """Displays the current configuration, masking sensitive data like API keys."""
    config, sources = get_config_with_source()
    if not config:
        warning("No configuration found.")
        with indent_context():
            tip("Use interactive configuration options (e.g., --db, --gemini) to set up TeshQ.")
        return

    # Implement a robust fallback mechanism for displaying config
    try:
        # First attempt: Try passing the dict directly
        print_config(config, "Current Configuration", mask_keys=["GEMINI_API_KEY"])
    except Exception:
        try:
            # Second attempt: Try passing the dict_items
            print_config(list(config.items()), "Current Configuration", mask_keys=["GEMINI_API_KEY"])
        except Exception:
            # Final fallback: Just print the config ourselves
            info("Current Configuration:")
            with indent_context():
                for key, value in config.items():
                    # Mask sensitive values
                    if key == "GEMINI_API_KEY" and value:
                        display_value = "********"
                    else:
                        display_value = value
                    info(f"{key}: {display_value}")

    space()
    info("Configuration Source:")
    with indent_context():
        for key, source in sources.items():
            info(f"{key}: {source}")


def configure_database_interactive() -> str:
    """
    Interactively configure the database connection.
    This will prompt the user for all DB details and construct the final DB URL.
    """
    info("Setting up database connection...")
    space()

    db_type = prompt("Database type", choices=SUPPORTED_DBS, default="postgresql").lower()
    if db_type == "sqlite":
        db_name = prompt("SQLite database file path", default="sqlite.db")
        return f"sqlite:///{db_name}"

    info(f"Configuring {db_type.upper()} connection...")
    db_user = prompt("Database username")
    while True:
        db_password = getpass("Database password: ")
        if not db_password:
            if not confirm("Empty password – is this correct?"):
                continue
        break
    db_host = prompt("Database host", default="localhost")
    default_port = 5432 if db_type == "postgresql" else 3306
    db_port = prompt("Database port", default=default_port, expected_type=int, validate=lambda p: 1 <= p <= 65535)
    db_name = prompt("Database name")
    safe_password = quote_plus(db_password)
    db_url = f"{db_type}://{db_user}:{safe_password}@{db_host}:{db_port}/{db_name}"

    try:
        url_obj = make_url(db_url)
        masked_url = str(url_obj._replace(password="********")) if url_obj.password else db_url
        info(f"Database URL: {masked_url}")
    except Exception:
        info("Database URL configured successfully.")

    return db_url


def configure_gemini_interactive() -> tuple:
    """
    Interactively configure Gemini API settings.
    Will prompt the user for the Gemini API key and model name.
    """
    info("Setting up Gemini API configuration...")
    space()

    while True:
        api_key = getpass("Gemini API Key (press Enter to skip): ")
        if api_key:
            break
        elif confirm("Skip Gemini API configuration?", default=True):
            api_key = None
            break
        else:
            warning("API key is required for Gemini functionality")
    model_name = prompt("Gemini model name", default=DEFAULT_GEMINI_MODEL)
    return api_key, model_name


@app.command()
def config(
    # Database options
    db_url: str = typer.Option(None, "--db-url", help="Full database URL (e.g. postgresql://user:pass@host:port/dbname)"),
    db_type_opt: str = typer.Option(
        None, "--db-type", help=f"Database type ({', '.join(SUPPORTED_DBS)})", case_sensitive=False
    ),
    db_user_opt: str = typer.Option(None, "--db-user", help="Database username"),
    db_password_opt: str = typer.Option(None, "--db-password", help="Database password (prompts if not set interactively)"),
    db_host_opt: str = typer.Option(None, "--db-host", help="Database host"),
    db_port_opt: int = typer.Option(None, "--db-port", help="Database port"),
    db_name_opt: str = typer.Option(None, "--db-name", help="Database name"),
    # Gemini options
    gemini_api_key_opt: str = typer.Option(None, "--gemini-api-key", help="Gemini API Key"),
    gemini_model_name_opt: str = typer.Option(
        DEFAULT_GEMINI_MODEL, "--gemini-model", help="Gemini model to use", show_default=True
    ),
    # Control flags
    save: bool = typer.Option(True, "--save/--no-save", help="Save configuration to files (i.e., .env and config.json)"),
    force_configure_db: bool = typer.Option(False, "--db", "-db", help="Interactive database configuration"),
    force_configure_gemini: bool = typer.Option(False, "--gemini", "-gemini", help="Interactive Gemini API configuration"),
    output_file_path: str = typer.Option(None, "--output-file-path", help="Output file path"),
    file_store_path: str = typer.Option(None, "--file-store-path", help="File store path"),
):
    """
    Configure TeshQ's database and Gemini API settings.

    You can use command-line options for automated (non-interactive) setup or use interactive
    configuration with flags like --db and --gemini.

    When saving, the resulting configuration is written to .env and config.json,
    ensuring all relevant environment variables and file paths persist for future sessions.
    """
    try:
        clear_screen()
        print_header("🔧 TESHQ CONFIGURATION", "Database & Gemini API Setup")

        final_db_url_to_save = None
        actual_gemini_api_key_to_save = gemini_api_key_opt
        actual_gemini_model_to_save = gemini_model_name_opt

        db_options_provided = any([db_url, db_type_opt, db_user_opt, db_password_opt, db_host_opt, db_port_opt, db_name_opt])
        file_path_options_provided = any([output_file_path, file_store_path])
        gemini_options_provided = gemini_api_key_opt is not None or gemini_model_name_opt != DEFAULT_GEMINI_MODEL

        action_taken = False

        # Database configuration logic
        if db_url:
            with section("Database Configuration"):
                info("Using provided database URL.")
                final_db_url_to_save = db_url
                action_taken = True
        elif force_configure_db:
            with section("Database Configuration"):
                try:
                    final_db_url_to_save = configure_database_interactive()
                    action_taken = True
                except KeyboardInterrupt:
                    warning("Database configuration cancelled.")
        elif db_options_provided:
            with section("Database Configuration"):
                info("Constructing database URL from provided options...")
                if not db_type_opt:
                    error("--db-type is required with individual database options.")
                    raise typer.Exit(1)
                db_type = db_type_opt.lower()
                if db_type not in SUPPORTED_DBS:
                    error(f"Unsupported database type: {db_type}")
                    raise typer.Exit(1)
                if db_type == "sqlite":
                    if not db_name_opt:
                        error("--db-name is required for SQLite.")
                        raise typer.Exit(1)
                    final_db_url_to_save = f"sqlite:///{db_name_opt}"
                else:
                    required_opts = [db_user_opt, db_host_opt, db_name_opt]
                    if not all(required_opts):
                        error("--db-user, --db-host, and --db-name are required for non-SQLite databases.")
                        raise typer.Exit(1)
                    password = db_password_opt if db_password_opt else getpass("Database password: ")
                    host = db_host_opt or "localhost"
                    port = db_port_opt or (5432 if db_type == "postgresql" else 3306)
                    safe_password = quote_plus(password)
                    final_db_url_to_save = f"{db_type}://{db_user_opt}:{safe_password}@{host}:{port}/{db_name_opt}"
                success("Database URL constructed successfully.")
                action_taken = True

        # Gemini configuration logic
        if force_configure_gemini:
            with section("Gemini API Configuration"):
                try:
                    api_key, model_name = configure_gemini_interactive()
                    actual_gemini_api_key_to_save = api_key
                    actual_gemini_model_to_save = model_name
                    action_taken = True
                except KeyboardInterrupt:
                    warning("Gemini configuration cancelled.")
        elif gemini_options_provided:
            with section("Gemini API Configuration"):
                info("Using provided Gemini API configuration.")
                action_taken = True

        # File Path Configuration
        if file_path_options_provided:
            with section("File Path Configuration"):
                info("Using provided file store path(s).")
                action_taken = True

        # Handle the command logic based on actions taken
        if not action_taken:
            with section("Current Configuration"):
                display_current_config()
                space()
                tip("Use --db or --gemini for interactive configuration, or provide options directly.")
                raise typer.Exit()

        # Save configuration if required
        if save:
            with section("Saving Configuration"):
                config_to_save = {}

                # Database
                if final_db_url_to_save:
                    config_to_save["DATABASE_URL"] = final_db_url_to_save

                # Gemini
                if force_configure_gemini or gemini_options_provided:
                    config_to_save["GEMINI_API_KEY"] = actual_gemini_api_key_to_save
                    config_to_save["GEMINI_MODEL_NAME"] = actual_gemini_model_to_save

                # Resolve and validate output file path
                if output_file_path:
                    resolved_output_path = os.path.abspath(output_file_path)
                    os.makedirs(os.path.dirname(resolved_output_path), exist_ok=True)
                    config_to_save["OUTPUT_PATH"] = resolved_output_path

                # Resolve and validate file store path
                if file_store_path:
                    resolved_file_store_path = os.path.abspath(file_store_path)
                    os.makedirs(os.path.dirname(resolved_file_store_path), exist_ok=True)  # Create parent dir too
                    config_to_save["FILE_STORE_PATH"] = resolved_file_store_path

                # Actually save to .env and config.json
                if config_to_save:
                    if save_config(config_to_save):
                        print_divider("Configuration Complete")
                        success("🎉 All configuration saved successfully!")
                        with indent_context():
                            tip("Run your TeshQ commands to start using the configured settings.")
                    else:
                        error("Some configuration files could not be saved.")
                        raise typer.Exit(1)
                else:
                    warning("No new configuration to save.")

        else:
            with section("Configuration Preview"):
                warning("Configuration not saved (--no-save specified).")
                if final_db_url_to_save:
                    info("Database URL would be saved.")
                if actual_gemini_api_key_to_save:
                    info("Gemini API configuration would be saved.")
                if file_path_options_provided:
                    info("File paths would be saved.")

    except Exception as e:
        error(f"An unexpected error occurred: {str(e)}")
        # Add more detailed debug info for troubleshooting
        if "--debug" in sys.argv:
            import traceback

            error("Debug traceback:")
            print(traceback.format_exc())
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
