"""
Configuration Command for TESH-Query CLI

This command sets up TeshQ's database, Gemini API, and file storage configuration.
It uses the consolidated configuration utilities from teshq/utils/config.py that retrieve and save settings
with fallback priorities from environment variables, ~/.teshq/.teshq.env (secrets), and ~/.teshq/config.yaml.

If `--save` is used, secrets (DATABASE_URL, GEMINI_API_KEY) are persisted to ~/.teshq/.teshq.env
and non-secret settings (model name, paths) are saved to ~/.teshq/config.yaml.
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
from teshq.utils.database_connectors import UnifiedDatabaseConnector
from teshq.utils.ui import print_config  # We'll implement our own fallback if this fails
from teshq.utils.ui import (  # handle_error,
    clear_screen,
    confirm,
    error,
    handle_error,
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
from teshq.utils.validation import ConfigValidator, validate_production_readiness

app = typer.Typer(invoke_without_command=True)
# Get supported database types from unified connector
SUPPORTED_DBS = UnifiedDatabaseConnector.get_supported_databases()


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


def configure_azure_interactive() -> dict:
    """
    Interactively configure Azure OpenAI settings.
    Prompts the user for the endpoint, deployment, API key, and API version.
    """
    info("Setting up Azure OpenAI configuration...")
    space()

    while True:
        api_key = getpass("Azure OpenAI API Key: ")
        if api_key:
            break
        warning("Azure OpenAI API key is required.")

    endpoint = prompt("Azure OpenAI Endpoint (e.g. https://<resource>.openai.azure.com/)")
    deployment = prompt("Azure OpenAI Deployment name (model deployment)")
    api_version = prompt("Azure OpenAI API Version", default="2024-02-01")

    return {
        "AZURE_OPENAI_API_KEY": api_key,
        "AZURE_OPENAI_ENDPOINT": endpoint,
        "AZURE_OPENAI_DEPLOYMENT": deployment,
        "AZURE_OPENAI_API_VERSION": api_version,
        "LLM_PROVIDER": "azure",
    }


@app.callback(invoke_without_command=True)
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
    # Azure OpenAI options
    azure_api_key_opt: str = typer.Option(None, "--azure-api-key", help="Azure OpenAI API key"),
    azure_endpoint_opt: str = typer.Option(None, "--azure-endpoint", help="Azure OpenAI endpoint URL"),
    azure_deployment_opt: str = typer.Option(None, "--azure-deployment", help="Azure OpenAI deployment name"),
    azure_api_version_opt: str = typer.Option(None, "--azure-api-version", help="Azure OpenAI API version (default: 2024-02-01)"),
    llm_provider_opt: str = typer.Option(None, "--llm-provider", help="LLM provider: 'google' (Gemini) or 'azure' (Azure OpenAI)"),
    # Control flags
    save: bool = typer.Option(True, "--save/--no-save", help="Save configuration to ~/.teshq/ (secrets → .teshq.env, settings → config.yaml)"),
    force_configure_db: bool = typer.Option(False, "--db", "-db", help="Interactive database configuration"),
    force_configure_gemini: bool = typer.Option(False, "--gemini", "-gemini", help="Interactive Gemini API configuration"),
    force_configure_azure: bool = typer.Option(False, "--azure", "-azure", help="Interactive Azure OpenAI configuration"),
    output_file_path: str = typer.Option(None, "--output-file-path", help="Output file path"),
    file_store_path: str = typer.Option(None, "--file-store-path", help="File store path"),
):
    """
    Configure TeshQ's database and LLM (Gemini or Azure OpenAI) settings.

    You can use command-line options for automated (non-interactive) setup or use interactive
    configuration with flags like --db, --gemini, or --azure.

    When saving, secrets (DATABASE_URL, GEMINI_API_KEY, AZURE_OPENAI_API_KEY) are written to ~/.teshq/.teshq.env
    and non-secret settings are stored in ~/.teshq/config.yaml,
    ensuring all relevant environment variables and file paths persist for future sessions.
    """
    try:
        clear_screen()
        print_header("🔧 TESHQ CONFIGURATION", "Database & LLM Setup")

        final_db_url_to_save = None
        actual_gemini_api_key_to_save = gemini_api_key_opt
        actual_gemini_model_to_save = gemini_model_name_opt
        azure_config_to_save: dict = {}

        db_options_provided = any([db_url, db_type_opt, db_user_opt, db_password_opt, db_host_opt, db_port_opt, db_name_opt])
        file_path_options_provided = any([output_file_path, file_store_path])
        gemini_options_provided = gemini_api_key_opt is not None or gemini_model_name_opt != DEFAULT_GEMINI_MODEL
        azure_options_provided = any([azure_api_key_opt, azure_endpoint_opt, azure_deployment_opt, azure_api_version_opt])

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

        # Azure OpenAI configuration logic
        if force_configure_azure:
            with section("Azure OpenAI Configuration"):
                try:
                    azure_config_to_save = configure_azure_interactive()
                    action_taken = True
                except KeyboardInterrupt:
                    warning("Azure OpenAI configuration cancelled.")
        elif azure_options_provided:
            with section("Azure OpenAI Configuration"):
                info("Using provided Azure OpenAI configuration.")
                azure_config_to_save = {
                    k: v for k, v in {
                        "AZURE_OPENAI_API_KEY": azure_api_key_opt,
                        "AZURE_OPENAI_ENDPOINT": azure_endpoint_opt,
                        "AZURE_OPENAI_DEPLOYMENT": azure_deployment_opt,
                        "AZURE_OPENAI_API_VERSION": azure_api_version_opt or "2024-02-01",
                        "LLM_PROVIDER": llm_provider_opt or "azure",
                    }.items() if v is not None
                }
                action_taken = True
        elif llm_provider_opt:
            # Just set the provider without full Azure config
            azure_config_to_save = {"LLM_PROVIDER": llm_provider_opt}
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
                tip("Use --db, --gemini, or --azure for interactive configuration, or provide options directly.")
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

                # Azure OpenAI
                if azure_config_to_save:
                    config_to_save.update(azure_config_to_save)

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

                # Save to ~/.teshq/ (secrets → .teshq.env, settings → config.yaml)
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
        handle_error(
            e,
            "Configuration Setup",
            show_traceback="--debug" in sys.argv,
            suggest_action="Check your input values and try again",
        )
        raise typer.Exit(1)


@app.command(name="validate", help="Validate current configuration for production readiness")
def validate_config():
    """Validate the current configuration for production deployment."""
    try:
        with section("Configuration Validation"):
            info("Checking configuration for production readiness...")

            # Get current configuration
            config, sources = get_config_with_source()

            if not config:
                error("No configuration found")
                tip("Run 'teshq config --interactive' to set up configuration")
                raise typer.Exit(1)

            # Validate configuration
            config_errors = ConfigValidator.validate_config(config)

            if config_errors:
                error("Configuration validation failed:")
                with indent_context():
                    for err in config_errors:
                        error(f"• {err}")
                tip("Run 'teshq config --interactive' to fix configuration issues")
                raise typer.Exit(1)

            # Test database connection
            if "DATABASE_URL" in config:
                with section("Database Connection Test"):
                    info("Testing database connection...")
                    is_connected, message = ConfigValidator.validate_database_connection(config["DATABASE_URL"])
                    if is_connected:
                        success(f"✅ {message}")
                    else:
                        error(f"❌ {message}")
                        tip("Check your database server and connection details")
                        raise typer.Exit(1)

            # Production readiness check
            with section("Production Readiness Assessment"):
                info("Evaluating production readiness...")
                is_ready, issues = validate_production_readiness(config)

                if is_ready:
                    success("🎉 Configuration is production-ready!")
                else:
                    warning("Configuration has production readiness issues:")
                    with indent_context():
                        for issue in issues:
                            if issue.startswith("WARNING"):
                                warning(f"• {issue}")
                            else:
                                error(f"• {issue}")

                    if any(not issue.startswith("WARNING") for issue in issues):
                        error("Critical issues must be resolved before production deployment")
                        raise typer.Exit(1)
                    else:
                        warning("Consider addressing warnings for optimal production setup")

            success("✅ Configuration validation completed successfully")

    except typer.Exit:
        raise
    except Exception as e:
        handle_error(
            e, "Configuration Validation", show_traceback=True, suggest_action="Check your configuration and try again"
        )
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
