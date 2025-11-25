"""
Configuration Command for TESH-Query CLI

This command provides a robust and safe way to manage TeshQ's configuration.
It ensures that updates are merged with existing settings, preventing accidental
data loss through a load-merge-save pattern.

Key Principles:
- **Load-Merge-Save Pattern:** Loads existing config, merges new values, saves complete result
- **User-Friendly Interactivity:** Both CLI flags and interactive prompts
- **Clear Feedback:** Shows current config and what changes will be applied
- **Preserved Settings:** Never accidentally removes existing configuration
"""

import os
import sys
from getpass import getpass
from urllib.parse import quote_plus

import typer
from sqlalchemy.engine.url import make_url

from teshq.utils.config import DEFAULT_GEMINI_MODEL, get_config, get_config_with_source, save_config
from teshq.utils.logging import configure_global_logger
from teshq.utils.ui import (
    confirm,
    error,
    handle_error,
    indent_context,
    info,
    print_config,
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


def mask_database_url(db_url: str) -> str:
    """Mask password in database URL for secure display."""
    try:
        url_obj = make_url(db_url)
        if url_obj.password:
            return str(url_obj._replace(password="********"))
        return db_url
    except Exception:
        # If parsing fails, just mask everything after ://
        if "://" in db_url:
            protocol = db_url.split("://")[0]
            return f"{protocol}://********"
        return "********"


def display_current_config():
    """Displays the current configuration, masking sensitive data like API keys and database URLs."""
    config, sources = get_config_with_source()
    if not config:
        warning("No configuration found.")
        with indent_context():
            tip("Use 'teshq config --interactive' to get started.")
        return

    # For security, always mask sensitive keys in any display.
    keys_to_mask = ["GEMINI_API_KEY", "DATABASE_URL"]

    info("Current Configuration:")
    with indent_context():
        for key, value in config.items():
            display_value = value
            if key in keys_to_mask and value:
                if key == "DATABASE_URL":
                    display_value = mask_database_url(value)
                else:
                    display_value = "********"
            info(f"{key}: {display_value}")

    space()
    info("Configuration Source:")
    with indent_context():
        for key, source in sources.items():
            info(f"{key}: {source}")


def display_config_status():
    """
    Display configuration status with formatted output for --show command.
    Shows database URL, Gemini model, API key status, and all other settings.
    """
    config, sources = get_config_with_source()

    if not config:
        warning("No configuration found.")
        space()
        with indent_context():
            tip("Run 'teshq config --interactive' to set up your configuration.")
        return

    print_header("📋 CONFIGURATION STATUS", "Current TeshQ Settings")

    # Database Configuration
    with section("Database Configuration"):
        db_url = config.get("DATABASE_URL")
        if db_url:
            masked_url = mask_database_url(db_url)
            info(f"Database URL: {masked_url}")

            # Extract database type from URL
            try:
                url_obj = make_url(db_url)
                info(f"Database Type: {url_obj.drivername}")
                info(f"Database Host: {url_obj.host or 'N/A'}")
                info(f"Database Name: {url_obj.database or 'N/A'}")
            except Exception:
                pass

            source = sources.get("DATABASE_URL", "Unknown")
            info(f"Source: {source}")
        else:
            warning("Database URL: Not configured")
            with indent_context():
                tip("Configure with: teshq config --db")

    space()

    # Gemini API Configuration
    with section("Gemini API Configuration"):
        api_key = config.get("GEMINI_API_KEY")
        model_name = config.get("GEMINI_MODEL_NAME", DEFAULT_GEMINI_MODEL)

        if api_key:
            success(f"API Key: Configured (ends with ...{api_key[-4:]})")
            source = sources.get("GEMINI_API_KEY", "Unknown")
            info(f"Source: {source}")
        else:
            warning("API Key: Not configured")
            with indent_context():
                tip("Configure with: teshq config --gemini")

        info(f"Model: {model_name}")
        if "GEMINI_MODEL_NAME" in sources:
            info(f"Source: {sources['GEMINI_MODEL_NAME']}")

    space()

    # File Path Configuration
    file_paths = {"OUTPUT_PATH": "Output File Path", "FILE_STORE_PATH": "File Store Path"}

    has_file_paths = any(config.get(key) for key in file_paths.keys())

    if has_file_paths:
        with section("File Path Configuration"):
            for key, label in file_paths.items():
                value = config.get(key)
                if value:
                    info(f"{label}: {value}")
                    if key in sources:
                        info(f"Source: {sources[key]}")
                    space()

    # Other Configuration
    other_keys = [
        k
        for k in config.keys()
        if k not in ["DATABASE_URL", "GEMINI_API_KEY", "GEMINI_MODEL_NAME", "OUTPUT_PATH", "FILE_STORE_PATH"]
    ]

    if other_keys:
        with section("Other Settings"):
            for key in other_keys:
                value = config[key]
                info(f"{key}: {value}")
                if key in sources:
                    info(f"Source: {sources[key]}")

    space()
    tip("Use 'teshq config --interactive' to modify settings.")


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
    db_password = getpass("Database password: ")
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


def configure_gemini_interactive(current_config: dict) -> tuple:
    """
    Interactively configure Gemini API settings, preserving existing values.
    Returns (api_key, model_name) tuple.
    """
    info("Setting up Gemini API configuration...")
    space()

    current_api_key = current_config.get("GEMINI_API_KEY")
    current_model = current_config.get("GEMINI_MODEL_NAME", DEFAULT_GEMINI_MODEL)

    prompt_text = "Enter new Gemini API Key (press Enter to keep existing key): "
    if not current_api_key:
        prompt_text = "Enter Gemini API Key: "

    api_key_input = getpass(prompt_text)
    final_api_key = api_key_input or current_api_key

    model_name = prompt("Gemini model name", default=current_model)
    return final_api_key, model_name


def configure_file_paths_interactive(current_config: dict) -> dict:
    """
    Interactively configure file paths, preserving existing values.
    Returns dict with OUTPUT_PATH and FILE_STORE_PATH.
    """
    info("Setting up file paths...")
    space()

    result = {}

    current_output = current_config.get("OUTPUT_PATH", "./output")
    if confirm("Configure output file path?", default=True):
        output_path = prompt("Output file path", default=current_output)
        result["OUTPUT_PATH"] = os.path.abspath(output_path)

    current_store = current_config.get("FILE_STORE_PATH", "./file_store")
    if confirm("Configure file store path?", default=True):
        store_path = prompt("File store path", default=current_store)
        result["FILE_STORE_PATH"] = os.path.abspath(store_path)

    return result


@app.command()
def config(
    # Database options
    db_url: str = typer.Option(None, "--db-url", help="Full database URL"),
    db_type_opt: str = typer.Option(None, "--db-type", help=f"Database type ({', '.join(SUPPORTED_DBS)})"),
    db_user_opt: str = typer.Option(None, "--db-user", help="Database username"),
    db_password_opt: str = typer.Option(None, "--db-password", help="Database password (prompts if not set)"),
    db_host_opt: str = typer.Option(None, "--db-host", help="Database host"),
    db_port_opt: int = typer.Option(None, "--db-port", help="Database port"),
    db_name_opt: str = typer.Option(None, "--db-name", help="Database name"),
    # Gemini options
    gemini_api_key_opt: str = typer.Option(None, "--gemini-api-key", help="Gemini API Key"),
    gemini_model_name_opt: str = typer.Option(None, "--gemini-model", help="Gemini model to use"),
    # File path options
    output_file_path: str = typer.Option(None, "--output-file-path", help="Output file path"),
    file_store_path: str = typer.Option(None, "--file-store-path", help="File store path"),
    # Control flags
    save: bool = typer.Option(True, "--save/--no-save", help="Save configuration to files"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Run full interactive configuration"),
    show: bool = typer.Option(False, "--show", help="Display current configuration status"),
    force_configure_db: bool = typer.Option(False, "--db", help="Run interactive database configuration only"),
    force_configure_gemini: bool = typer.Option(False, "--gemini", help="Run interactive Gemini API configuration only"),
    log: bool = typer.Option(False, "--log", help="Enable real-time logging output"),
):
    """
    Configure TeshQ's database, Gemini API, and other settings safely.

    Uses a load-merge-save pattern to safely update configuration without losing
    existing settings. When you update one setting (e.g., --gemini-api-key), all
    other settings are preserved.

    Examples:
        teshq config                           # Smart assistant mode
        teshq config --show                    # Display current configuration
        teshq config --interactive             # Full interactive setup
        teshq config --db                      # Configure database only
        teshq config --gemini                  # Configure Gemini API only
        teshq config --gemini-api-key <key>    # Set API key via flag
    """
    configure_global_logger(enable_cli_output=log)
    from teshq.utils.logging import logger

    logger.info("Starting configuration command with load-merge-save pattern")

    try:
        # === SHOW MODE: Display configuration and exit ===
        if show:
            display_config_status()
            raise typer.Exit()

        # === STEP 1: LOAD EXISTING CONFIGURATION ===
        config_to_save = get_config()
        logger.info(f"Loaded existing configuration keys: {list(config_to_save.keys())}")

        action_taken = False
        db_options_provided = any([db_url, db_type_opt, db_user_opt, db_host_opt, db_port_opt, db_name_opt])
        gemini_options_provided = gemini_api_key_opt is not None or gemini_model_name_opt is not None
        file_path_options_provided = any([output_file_path, file_store_path])

        # === STEP 2: MERGE NEW CONFIGURATION ===

        # --- Interactive Mode ---
        if interactive:
            print_header("🔧 TESHQ CONFIGURATION", "Safe Database & Gemini API Setup")
            action_taken = True
            with section("Full Interactive Configuration"):
                if confirm("Configure database connection?"):
                    db_url_result = configure_database_interactive()
                    if db_url_result:
                        config_to_save["DATABASE_URL"] = db_url_result

                if confirm("Configure Gemini API?"):
                    api_key_res, model_name_res = configure_gemini_interactive(config_to_save)
                    if api_key_res:
                        config_to_save["GEMINI_API_KEY"] = api_key_res
                    if model_name_res:
                        config_to_save["GEMINI_MODEL_NAME"] = model_name_res

                if confirm("Configure file paths?"):
                    file_paths = configure_file_paths_interactive(config_to_save)
                    config_to_save.update(file_paths)

        # --- Flag-Based Mode ---
        elif any(
            [
                db_options_provided,
                gemini_options_provided,
                file_path_options_provided,
                force_configure_db,
                force_configure_gemini,
            ]
        ):
            print_header("🔧 TESHQ CONFIGURATION", "Safe Database & Gemini API Setup")

            # --- Database Configuration ---
            if db_url:
                info("Applying database URL from --db-url flag.")
                config_to_save["DATABASE_URL"] = db_url
                action_taken = True
            elif force_configure_db:
                with section("Interactive Database Configuration"):
                    try:
                        db_url_result = configure_database_interactive()
                        if db_url_result:
                            config_to_save["DATABASE_URL"] = db_url_result
                        action_taken = True
                    except KeyboardInterrupt:
                        warning("Database configuration cancelled.")
            elif db_options_provided:
                with section("Database Configuration from Flags"):
                    info("Constructing database URL from provided --db-* flags...")
                    if not db_type_opt:
                        error("--db-type is required with other --db-* options.")
                        raise typer.Exit(1)

                    db_type = db_type_opt.lower()
                    if db_type not in SUPPORTED_DBS:
                        error(f"Unsupported database type: {db_type}")
                        raise typer.Exit(1)

                    if db_type == "sqlite":
                        if not db_name_opt:
                            error("--db-name is required for SQLite.")
                            raise typer.Exit(1)
                        config_to_save["DATABASE_URL"] = f"sqlite:///{db_name_opt}"
                    else:
                        required_opts = [db_user_opt, db_host_opt, db_name_opt]
                        if not all(required_opts):
                            error("--db-user, --db-host, and --db-name are required for non-SQLite databases.")
                            raise typer.Exit(1)

                        password = db_password_opt or getpass("Database password: ")
                        safe_password = quote_plus(password)
                        port = db_port_opt or (5432 if db_type == "postgresql" else 3306)

                        config_to_save["DATABASE_URL"] = (
                            f"{db_type}://{db_user_opt}:{safe_password}@{db_host_opt}:{port}/{db_name_opt}"
                        )

                    info("Database URL constructed successfully.")
                    action_taken = True

            # --- Gemini Configuration ---
            if force_configure_gemini:
                with section("Interactive Gemini API Configuration"):
                    try:
                        api_key, model_name = configure_gemini_interactive(config_to_save)
                        if api_key:
                            config_to_save["GEMINI_API_KEY"] = api_key
                        if model_name:
                            config_to_save["GEMINI_MODEL_NAME"] = model_name
                        action_taken = True
                    except KeyboardInterrupt:
                        warning("Gemini configuration cancelled.")
            elif gemini_options_provided:
                with section("Gemini API Configuration from Flags"):
                    if gemini_api_key_opt is not None:
                        config_to_save["GEMINI_API_KEY"] = gemini_api_key_opt
                        info("Updated Gemini API Key.")
                        action_taken = True
                    if gemini_model_name_opt is not None:
                        config_to_save["GEMINI_MODEL_NAME"] = gemini_model_name_opt
                        info(f"Updated Gemini Model to: {gemini_model_name_opt}")
                        action_taken = True

            # --- File Path Configuration ---
            if file_path_options_provided:
                with section("File Path Configuration from Flags"):
                    if output_file_path:
                        resolved_path = os.path.abspath(output_file_path)
                        config_to_save["OUTPUT_PATH"] = resolved_path
                        info(f"Set output path to: {resolved_path}")
                        action_taken = True
                    if file_store_path:
                        resolved_path = os.path.abspath(file_store_path)
                        config_to_save["FILE_STORE_PATH"] = resolved_path
                        info(f"Set file store path to: {resolved_path}")
                        action_taken = True

        # === STEP 3: SMART ASSISTANT MODE (NO FLAGS OR OPTIONS) ===
        if not any([action_taken, interactive, force_configure_db, force_configure_gemini]):
            # When user runs just `teshq config`, show status and offer smart setup
            config = get_config()

            # Check what's missing
            needs_db = not config.get("DATABASE_URL")
            needs_gemini = not config.get("GEMINI_API_KEY")
            needs_anything = needs_db or needs_gemini

            if needs_anything:
                # First-time setup flow
                print_header("👋 WELCOME TO TESHQ", "Let's get you set up!")
                space()

                if needs_db:
                    warning("⚠️  Database not configured")
                if needs_gemini:
                    warning("⚠️  Gemini API not configured")

                space()
                info("I can help you set this up interactively, or you can use specific commands:")
                with indent_context():
                    tip("Run 'teshq config --interactive' for guided setup")
                    tip("Run 'teshq config --db' to configure database only")
                    tip("Run 'teshq config --gemini' to configure Gemini API only")
                    tip("Run 'teshq config --show' to see detailed status")

                space()
                if confirm("Would you like to start the interactive setup now?", default=True):
                    # Launch interactive mode
                    action_taken = True
                    interactive = True
                    space()
                    with section("Full Interactive Configuration"):
                        if needs_db or confirm("Configure database connection?"):
                            db_url_result = configure_database_interactive()
                            if db_url_result:
                                config_to_save["DATABASE_URL"] = db_url_result

                        if needs_gemini or confirm("Configure Gemini API?"):
                            api_key_res, model_name_res = configure_gemini_interactive(config_to_save)
                            if api_key_res:
                                config_to_save["GEMINI_API_KEY"] = api_key_res
                            if model_name_res:
                                config_to_save["GEMINI_MODEL_NAME"] = model_name_res

                        if confirm("Configure file paths?"):
                            file_paths = configure_file_paths_interactive(config_to_save)
                            config_to_save.update(file_paths)
                else:
                    info("No problem! Run 'teshq config --help' to see all options.")
                    raise typer.Exit()
            else:
                # Already configured - show status
                display_config_status()
                space()
                info("Your configuration looks good! 🎉")
                with indent_context():
                    tip("Use 'teshq config --interactive' to modify settings")
                    tip("Use 'teshq config --show' for detailed status")
                raise typer.Exit()

        # === STEP 4: SAVE OR PREVIEW ===
        if save and action_taken:
            with section("Saving Merged Configuration"):
                if config_to_save.get("OUTPUT_PATH"):
                    os.makedirs(os.path.dirname(config_to_save["OUTPUT_PATH"]), exist_ok=True)
                if config_to_save.get("FILE_STORE_PATH"):
                    os.makedirs(config_to_save["FILE_STORE_PATH"], exist_ok=True)

                if save_config(config_to_save):
                    success("🎉 Configuration saved successfully!")
                    space()
                    with section("Updated Configuration"):
                        display_current_config()
                else:
                    error("Failed to save one or more configuration files.")
                    raise typer.Exit(1)
        elif not save and action_taken:
            with section("Configuration Preview (Not Saved)"):
                warning("Running in preview mode. The following changes will NOT be saved.")
                print_config(config_to_save, "Preview of Merged Configuration", mask_keys=["GEMINI_API_KEY", "DATABASE_URL"])

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        warning("\nOperation cancelled by user.")
        sys.exit(130)
    except Exception as e:
        handle_error(
            e,
            "Configuration Setup",
            show_traceback="--debug" in sys.argv,
            suggest_action="Check your input values and file permissions, then try again.",
        )
        raise typer.Exit(1)


@app.command(name="validate")
def validate_config(log: bool = typer.Option(False, "--log")):
    """Validate the current configuration for production readiness."""
    # Validation logic placeholder
    pass


if __name__ == "__main__":
    app()
